# File: server.py (for Render)
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import FileResponse
import uvicorn
import json
import base64

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.web_clients: dict[str, WebSocket] = {}
        self.local_worker: WebSocket | None = None

    async def connect_web_client(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.web_clients[user_id] = websocket

    async def connect_local_worker(self, websocket: WebSocket):
        await websocket.accept()
        self.local_worker = websocket
        for client in self.web_clients.values():
            await client.send_json({"type": "status", "data": "AI worker connected. Ready to upload."})

    def disconnect_web_client(self, user_id: str):
        if user_id in self.web_clients:
            del self.web_clients[user_id]

    async def disconnect_local_worker(self):
        self.local_worker = None
        for client in self.web_clients.values():
            try:
                await client.send_json({"type": "status", "data": "AI worker disconnected. Please refresh."})
            except Exception:
                pass # Client might already be disconnected
        print("Worker disconnected.")

    async def forward_to_worker(self, message: str):
        if self.local_worker:
            await self.local_worker.send_text(message)
        else:
            print("Attempted to send to worker, but worker is not connected.")

    async def forward_to_web_client(self, message: str):
        try:
            data = json.loads(message)
            user_id = data.get("user_id")
            if user_id and user_id in self.web_clients:
                await self.web_clients[user_id].send_text(message)
        except Exception as e:
            print(f"Error forwarding to web client: {e}")

manager = ConnectionManager()

@app.get("/")
async def get_homepage():
    return FileResponse('index.html')

@app.get("/status")
async def get_status():
    return {"worker_connected": manager.local_worker is not None}

@app.post("/upload/{user_id}")
async def http_upload_pdf(user_id: str, file: UploadFile = File(...)):
    if not manager.local_worker:
        return {"error": "Local AI worker is not connected."}
    content = await file.read()
    content_base64 = base64.b64encode(content).decode('utf-8')
    await manager.forward_to_worker(json.dumps({
        "type": "upload", "user_id": user_id,
        "filename": file.filename, "data": content_base64
    }))
    return {"message": "File sent to worker for processing."}

@app.post("/remove_watermark/{user_id}")
async def http_remove_watermark(user_id: str, image: UploadFile = File(...), mask: UploadFile = File(...)):
    if not manager.local_worker:
        return {"error": "Local AI worker is not connected."}
    image_content = await image.read()
    mask_content = await mask.read()
    image_base64 = base64.b64encode(image_content).decode('utf-8')
    mask_base64 = base64.b64encode(mask_content).decode('utf-8')
    await manager.forward_to_worker(json.dumps({
        "type": "remove_watermark_manual", "user_id": user_id,
        "image": image_base64, "mask": mask_base64
    }))
    return {"message": "Image and mask sent to worker for processing."}


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
            data['user_id'] = user_id
            await manager.forward_to_worker(json.dumps(data))
    except WebSocketDisconnect:
        manager.disconnect_web_client(user_id)
        print(f"Web client {user_id} disconnected.")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
