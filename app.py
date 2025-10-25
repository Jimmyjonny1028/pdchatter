# File: server.py (This is the code that should be on Render)
# Final version with ChatPDF and General AI Chat endpoints.

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import uvicorn
import json
import base64
import datetime

app = FastAPI()

def log_message(msg):
    """Helper function for timestamped logs."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")

class ConnectionManager:
    def __init__(self):
        self.web_clients: dict[str, WebSocket] = {}
        self.local_worker: WebSocket | None = None

    async def connect_web_client(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.web_clients[user_id] = websocket
        log_message(f"Web client '{user_id}' connected.")

    async def connect_local_worker(self, websocket: WebSocket):
        await websocket.accept()
        self.local_worker = websocket
        log_message(">>> Local AI Worker connected! <<<")

    def disconnect_web_client(self, user_id: str):
        if user_id in self.web_clients:
            del self.web_clients[user_id]
        log_message(f"Web client '{user_id}' disconnected.")

    async def disconnect_local_worker(self):
        self.local_worker = None
        log_message(">>> Local AI Worker disconnected. <<<")

    async def forward_to_worker(self, message: str):
        if self.local_worker and self.local_worker.client_state.name == 'CONNECTED':
            await self.local_worker.send_text(message)
        else:
            log_message("!!! ERROR: Worker not connected. Cannot forward message. !!!")

    async def forward_to_web_client(self, message: str):
        try:
            data = json.loads(message)
            msg_type = data.get("type", "unknown")
            user_id = data.get("user_id")
            
            if msg_type == "ping":
                return
            
            if user_id and user_id in self.web_clients:
                await self.web_clients[user_id].send_text(message)
        except Exception as e:
            log_message(f"!!! CRITICAL ERROR in forward_to_web_client: {e}")

manager = ConnectionManager()

@app.get("/")
async def get_homepage():
    return FileResponse('index.html')

@app.get("/status")
async def get_status():
    is_connected = manager.local_worker is not None and manager.local_worker.client_state.name == 'CONNECTED'
    return {"worker_connected": is_connected}

@app.post("/upload/{user_id}")
async def http_upload_pdf(user_id: str, file: UploadFile = File(...)):
    if not manager.local_worker:
        raise HTTPException(status_code=503, detail="Local AI worker is not connected.")
    
    content = await file.read()
    content_base64 = base64.b64encode(content).decode('utf-8')
    
    CHUNK_SIZE = 512 * 1024
    
    await manager.forward_to_worker(json.dumps({ "type": "upload_start", "user_id": user_id, "filename": file.filename }))
    for i in range(0, len(content_base64), CHUNK_SIZE):
        await manager.forward_to_worker(json.dumps({ "type": "upload_chunk", "user_id": user_id, "data": content_base64[i:i + CHUNK_SIZE] }))
    await manager.forward_to_worker(json.dumps({ "type": "upload_end", "user_id": user_id }))
    
    return {"message": "File sent to worker for processing."}

@app.websocket("/ws/worker")
async def worker_websocket(websocket: WebSocket):
    await manager.connect_local_worker(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.forward_to_web_client(data)
    except WebSocketDisconnect:
        await manager.disconnect_local_worker()

@app.websocket("/ws/web/{user_id}")
async def web_client_websocket(websocket: WebSocket, user_id: str):
    await manager.connect_web_client(websocket, user_id)
    try:
        while True:
            data_text = await websocket.receive_text()
            data = json.loads(data_text)
            
            if data.get("type") == "ping":
                continue
            
            data['user_id'] = user_id
            await manager.forward_to_worker(json.dumps(data))
    except WebSocketDisconnect:
        manager.disconnect_web_client(user_id)
