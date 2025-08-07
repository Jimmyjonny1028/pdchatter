# File: server.py (for Render)
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
import uvicorn
import json

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        # Manages multiple web clients, identified by a unique user ID
        self.web_clients: dict[str, WebSocket] = {}
        self.local_worker: WebSocket | None = None

    async def connect_web_client(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.web_clients[user_id] = websocket

    async def connect_local_worker(self, websocket: WebSocket):
        await websocket.accept()
        self.local_worker = websocket
        # Notify all connected clients that the worker is online
        for client in self.web_clients.values():
            await client.send_json({"type": "status", "data": "AI worker connected. Ready to upload."})

    def disconnect_web_client(self, user_id: str):
        if user_id in self.web_clients:
            del self.web_clients[user_id]

    async def disconnect_local_worker(self):
        self.local_worker = None
        # Notify all connected clients that the worker is offline
        for client in self.web_clients.values():
            try:
                await client.send_json({"type": "status", "data": "AI worker disconnected. Please refresh."})
            except Exception:
                pass # Client might already be disconnected
        print("Worker disconnected.")

    async def forward_to_worker(self, message: str):
        """Forwards a message from a web client to the local worker."""
        if self.local_worker:
            await self.local_worker.send_text(message)
        else:
            print("Attempted to send to worker, but worker is not connected.")

    async def forward_to_web_client(self, message: str):
        """Forwards a message from the local worker to the correct web client."""
        try:
            data = json.loads(message)
            user_id = data.get("user_id")
            if user_id and user_id in self.web_clients:
                await self.web_clients[user_id].send_text(message)
            else:
                print(f"Could not find web client for user_id: {user_id}")
        except Exception as e:
            print(f"Error forwarding to web client: {e}")

manager = ConnectionManager()

@app.get("/")
async def get_homepage():
    """Serves the main HTML file."""
    return FileResponse('index.html')

@app.websocket("/ws/worker")
async def worker_websocket(websocket: WebSocket):
    """Endpoint for your local PC to connect to."""
    await manager.connect_local_worker(websocket)
    try:
        while True:
            # Worker sends results, which we forward to the correct web client
            data = await websocket.receive_text()
            await manager.forward_to_web_client(data)
    except WebSocketDisconnect:
        await manager.disconnect_local_worker()

@app.websocket("/ws/web/{user_id}")
async def web_client_websocket(websocket: WebSocket, user_id: str):
    """Endpoint for the website/browser to connect to."""
    await manager.connect_web_client(websocket, user_id)
    if not manager.local_worker:
        await websocket.send_json({"type": "status", "data": "Waiting for local AI worker to connect..."})
    else:
        await websocket.send_json({"type": "status", "data": "AI worker connected. Ready to upload."})
        # Use json.dumps to ensure the message is a string
        await manager.forward_to_worker(json.dumps({"type": "list_chats", "user_id": user_id}))
        
    try:
        while True:
            # The website sends tasks, which we forward to the local worker
            data_text = await websocket.receive_text()
            data = json.loads(data_text)
            data['user_id'] = user_id
            # Forward the message as a JSON string
            await manager.forward_to_worker(json.dumps(data))
    except WebSocketDisconnect:
        manager.disconnect_web_client(user_id)
        print(f"Web client {user_id} disconnected.")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
