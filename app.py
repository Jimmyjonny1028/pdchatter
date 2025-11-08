# File: app.py (Firebase Firestore Version - Worker Authentication Added + /token fix)

import asyncio
import websockets
import json
import base64
import datetime
import bcrypt
import jwt
import os
import firebase_admin
from firebase_admin import credentials, firestore
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException, Body, Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

# --- CONFIGURATION & SECURITY ---
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "a_very_secret_key_for_development_only")

# Get worker secret key from environment
WORKER_SECRET_KEY = os.environ.get("WORKER_SECRET_KEY")
if not WORKER_SECRET_KEY:
    print("WARNING: WORKER_SECRET_KEY not set. Worker connections will be insecure.")
    # In production, you might want to enforce it strictly:
    # raise ValueError("WORKER_SECRET_KEY environment variable is required!")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
WORKER_AUTH_TIMEOUT = 10  # seconds

# --- FIREBASE INITIALIZATION ---
try:
    encoded_key = os.environ.get("FIREBASE_SERVICE_ACCOUNT_BASE64")
    if not encoded_key:
        raise ValueError("FIREBASE_SERVICE_ACCOUNT_BASE64 environment variable not set.")

    decoded_key = base64.b64decode(encoded_key).decode("utf-8")
    service_account_info = json.loads(decoded_key)
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    users_collection = db.collection("users")
    chats_collection = db.collection("chats")
    print("✅ Connected to Firebase Firestore.")
except Exception as e:
    print(f"FATAL: Could not initialize Firebase Admin SDK. Error: {e}")

# --- JWT CREATION ---
def create_access_token(data: dict, expires_delta: datetime.timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.timezone.utc) + (
        expires_delta or datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)

# --- Dependency: Get current user from JWT ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid credentials.")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")

app = FastAPI()

# --- HELPERS ---
def get_password_hash(password): return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
def verify_password(plain, hashed): return bcrypt.checkpw(plain.encode(), hashed.encode())

def log_message(msg):
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

# --- CONNECTION MANAGER ---
class ConnectionManager:
    def __init__(self):
        self.web_clients: dict[str, WebSocket] = {}
        self.local_worker: WebSocket | None = None

    async def connect_web_client(self, websocket: WebSocket, user_id: str):
        self.web_clients[user_id] = websocket
        log_message(f"🌐 Web client '{user_id}' connected.")

    async def connect_local_worker(self, websocket: WebSocket):
        self.local_worker = websocket
        log_message("🤖 Local AI Worker Authenticated and Connected!")

    def disconnect_web_client(self, user_id: str):
        self.web_clients.pop(user_id, None)
        log_message(f"🌐 Web client '{user_id}' disconnected.")

    async def disconnect_local_worker(self):
        self.local_worker = None
        log_message("🤖 Local AI Worker disconnected.")

    async def forward_to_worker(self, message: str):
        if self.local_worker and self.local_worker.client_state.name == "CONNECTED":
            await self.local_worker.send_text(message)
        else:
            log_message("❌ Worker not connected — cannot forward message.")
            try:
                msg = json.loads(message)
                user_id = msg.get("user_id")
                if user_id and user_id in self.web_clients:
                    await self.web_clients[user_id].send_text(json.dumps({
                        "type": "error",
                        "user_id": user_id,
                        "data": "AI worker not connected. Please ensure worker.py is running and authenticated."
                    }))
            except Exception as e:
                log_message(f"Could not notify client: {e}")

    async def forward_to_web_client(self, message: str):
        try:
            data = json.loads(message)
            user_id = data.get("user_id")
            if data.get("type") == "ping":
                return
            if user_id and user_id in self.web_clients:
                await self.web_clients[user_id].send_text(message)
        except Exception as e:
            log_message(f"⚠️ Error forwarding to web client: {e}")

manager = ConnectionManager()

# --- MODELS ---
class ChatMessage(BaseModel):
    sender: str
    text: str
    imageB64: Optional[str] = None

class ChatData(BaseModel):
    id: str
    name: str
    type: str
    timestamp: str
    history: List[ChatMessage]
    pdfName: Optional[str] = None

# --- ROUTES ---
@app.get("/")
async def get_homepage():
    return FileResponse("index.html")

@app.get("/status")
async def get_status():
    is_connected = manager.local_worker and manager.local_worker.client_state.name == "CONNECTED"
    return {"worker_connected": bool(is_connected)}

@app.post("/signup")
async def signup(user_data: dict = Body(...)):
    username, password = user_data.get("username"), user_data.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required.")
    if users_collection.document(username).get().exists:
        raise HTTPException(status_code=400, detail="Username already exists.")
    users_collection.document(username).set({"username": username, "password": get_password_hash(password)})
    log_message(f"🆕 User signed up: {username}")
    return {"message": "User created successfully."}

@app.post("/login")
async def login(user_data: dict = Body(...)):
    username, password = user_data.get("username"), user_data.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Missing credentials.")
    doc = users_collection.document(username).get()
    if not doc.exists:
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    user = doc.to_dict()
    if not verify_password(password, user["password"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    token = create_access_token({"sub": username})
    return {"access_token": token, "token_type": "bearer"}

# ✅ ADD TOKEN ALIAS FIX HERE
@app.post("/token")
async def token_alias(user_data: dict = Body(...)):
    """Alias endpoint for OAuth2 clients expecting /token instead of /login."""
    return await login(user_data)

@app.post("/upload/{user_id}")
async def upload_pdf(user_id: str, file: UploadFile = File(...)):
    if not manager.local_worker:
        raise HTTPException(status_code=503, detail="Worker not connected.")
    content = await file.read()
    content_base64 = base64.b64encode(content).decode()
    CHUNK = 512 * 1024
    await manager.forward_to_worker(json.dumps({"type": "upload_start", "user_id": user_id, "filename": file.filename}))
    for i in range(0, len(content_base64), CHUNK):
        await manager.forward_to_worker(json.dumps({
            "type": "upload_chunk", "user_id": user_id, "data": content_base64[i:i+CHUNK]
        }))
    await manager.forward_to_worker(json.dumps({"type": "upload_end", "user_id": user_id}))
    return {"message": "File uploaded to worker."}

# --- WEBSOCKETS ---
@app.websocket("/ws/worker")
async def worker_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        auth_data_str = await asyncio.wait_for(websocket.receive_text(), timeout=WORKER_AUTH_TIMEOUT)
        auth = json.loads(auth_data_str)
        if WORKER_SECRET_KEY:
            if auth.get("type") == "auth" and auth.get("secret") == WORKER_SECRET_KEY:
                await manager.connect_local_worker(websocket)
            else:
                log_message("🚫 Worker auth failed.")
                await websocket.close(code=1008, reason="Invalid secret")
                return
        else:
            log_message("⚠️ Worker connected without auth key.")
            await manager.connect_local_worker(websocket)
        while True:
            data = await websocket.receive_text()
            await manager.forward_to_web_client(data)
    except asyncio.TimeoutError:
        log_message("Worker failed to authenticate in time.")
        await websocket.close(code=1008, reason="Timeout")
    except WebSocketDisconnect:
        await manager.disconnect_local_worker()
    except Exception as e:
        log_message(f"Worker WS error: {e}")
        await manager.disconnect_local_worker()

@app.websocket("/ws/web")
async def web_client_websocket(websocket: WebSocket):
    await websocket.accept()
    user_id = None
    try:
        auth_str = await asyncio.wait_for(websocket.receive_text(), timeout=30)
        auth = json.loads(auth_str)
        token = auth.get("token")
        if token:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if not user_id:
                await websocket.close(code=1008, reason="Invalid token payload")
                return
        else:
            user_id = auth.get("user_id")
            if not user_id:
                await websocket.close(code=1008, reason="Missing user_id")
                return

        await manager.connect_web_client(websocket, user_id)
        await websocket.send_text(json.dumps({"type": "auth_success", "user_id": user_id}))
        while True:
            data = json.loads(await websocket.receive_text())
            if data.get("type") != "ping":
                data["user_id"] = user_id
                await manager.forward_to_worker(json.dumps(data))
    except WebSocketDisconnect:
        if user_id:
            manager.disconnect_web_client(user_id)
    except Exception as e:
        log_message(f"Web client error: {e}")
        if user_id:
            manager.disconnect_web_client(user_id)

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=10000)
