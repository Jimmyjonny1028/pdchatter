# File: server.py (for Render)
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
import uvicorn
import json

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

    def disconnect_web_client(self, user_id: str):
        if user_id in self.web_clients:
            del self.web_clients[user_id]

    async def disconnect_local_worker(self):
        self.local_worker = None
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
    """A simple endpoint for the website to check if the worker is connected."""
    return {"worker_connected": manager.local_worker is not None}

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
