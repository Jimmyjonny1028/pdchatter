# File: server.py (for Render)
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
import uvicorn

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.web_client: WebSocket | None = None
        self.local_worker: WebSocket | None = None

    async def connect_web_client(self, websocket: WebSocket):
        await websocket.accept()
        self.web_client = websocket

    async def connect_local_worker(self, websocket: WebSocket):
        await websocket.accept()
        self.local_worker = websocket
        if self.web_client:
            await self.web_client.send_json({"type": "status", "data": "AI worker connected. Ready to upload."})

    def disconnect_web_client(self):
        self.web_client = None

    def disconnect_local_worker(self):
        self.local_worker = None
        print("Worker disconnected.")


manager = ConnectionManager()

@app.get("/")
async def get_homepage():
    return FileResponse('index.html')

@app.websocket("/ws/worker")
async def worker_websocket(websocket: WebSocket):
    await manager.connect_local_worker(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if manager.web_client:
                await manager.web_client.send_json(data)
    except WebSocketDisconnect:
        manager.disconnect_local_worker()

@app.websocket("/ws/web")
async def web_client_websocket(websocket: WebSocket):
    await manager.connect_web_client(websocket)
    if not manager.local_worker:
        await manager.web_client.send_json({"type": "status", "data": "Waiting for local AI worker to connect..."})
    else:
        await manager.web_client.send_json({"type": "status", "data": "AI worker connected. Ready to upload."})

    try:
        while True:
            data = await websocket.receive_json()
            if manager.local_worker:
                await manager.local_worker.send_json(data)
            else:
                await manager.web_client.send_json({"type": "error", "data": "Local AI worker is not connected."})
    except WebSocketDisconnect:
        manager.disconnect_web_client()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)