import asyncio
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

# === CONFIG ===
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev_secret_key")
WORKER_SECRET_KEY = os.environ.get("WORKER_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
WORKER_AUTH_TIMEOUT = 10

# === FIREBASE ===
try:
    encoded_key = os.environ.get("FIREBASE_SERVICE_ACCOUNT_BASE64")
    decoded_key = base64.b64decode(encoded_key).decode("utf-8")
    cred = credentials.Certificate(json.loads(decoded_key))
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    users = db.collection("users")
    chats = db.collection("chats")
    print("✅ Firebase initialized")
except Exception as e:
    print("⚠️ Firebase init failed:", e)

# === JWT ===
def create_access_token(data: dict):
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    data.update({"exp": expire})
    return jwt.encode(data, JWT_SECRET_KEY, algorithm=ALGORITHM)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

# === HELPERS ===
def hash_pw(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_pw(p, h): return bcrypt.checkpw(p.encode(), h.encode())
def log(msg): print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

# === FASTAPI ===
app = FastAPI()

# === WS MANAGER ===
class ConnectionManager:
    def __init__(self):
        self.web_clients: Dict[str, WebSocket] = {}
        self.worker: Optional[WebSocket] = None

    async def send_to_worker(self, msg: str):
        if self.worker and self.worker.client_state.name == "CONNECTED":
            await self.worker.send_text(msg)
        else:
            data = json.loads(msg)
            uid = data.get("user_id")
            if uid in self.web_clients:
                await self.web_clients[uid].send_text(json.dumps({
                    "type": "error", "data": "AI worker not connected."
                }))

manager = ConnectionManager()

# === MODELS ===
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

# === ROUTES ===
@app.get("/")
async def home():
    return FileResponse("index.html")

@app.get("/status")
async def status():
    return {
        "worker_connected": bool(manager.worker and manager.worker.client_state.name == "CONNECTED"),
        "clients": list(manager.web_clients.keys())
    }

# --- Signup/Login (both /signup + /auth/signup supported) ---
@app.post("/signup")
@app.post("/auth/signup")
async def signup(user: dict = Body(...)):
    u, p = user.get("username"), user.get("password")
    if not u or not p:
        raise HTTPException(status_code=400, detail="Missing credentials.")
    if users.document(u).get().exists:
        raise HTTPException(status_code=400, detail="Username exists.")
    users.document(u).set({"username": u, "password": hash_pw(p)})
    return {"message": "User created."}

@app.post("/login")
@app.post("/auth/login")
@app.post("/token")  # alias
async def login(user: dict = Body(...)):
    u, p = user.get("username"), user.get("password")
    doc = users.document(u).get()
    if not doc.exists or not verify_pw(p, doc.to_dict()["password"]):
        raise HTTPException(status_code=401, detail="Invalid username/password.")
    token = create_access_token({"sub": u})
    return {"access_token": token, "token_type": "bearer"}

# --- Chats ---
@app.get("/chats")
async def list_chats(current_user: str = Depends(get_current_user)):
    q = chats.where("userId", "==", current_user).order_by("timestamp", direction=firestore.Query.DESCENDING)
    data = [doc.to_dict() for doc in q.stream()]
    return data

@app.post("/chats")
async def save_chat(chat: ChatData, current_user: str = Depends(get_current_user)):
    d = chat.dict(); d["userId"] = current_user
    chats.document(f"{current_user}_{chat.id}").set(d)
    return {"message": "Saved"}

# --- Upload PDF ---
@app.post("/upload/{user_id}")
async def upload_pdf(user_id: str, file: UploadFile = File(...)):
    if not manager.worker:
        raise HTTPException(status_code=503, detail="Worker not connected.")
    data = base64.b64encode(await file.read()).decode()
    await manager.send_to_worker(json.dumps({"type": "upload", "user_id": user_id, "data": data}))
    return {"message": "File sent to worker."}

# === WEBSOCKETS ===
@app.websocket("/ws")
@app.websocket("/ws/web")
async def ws_web(websocket: WebSocket):
    await websocket.accept()
    try:
        auth = await asyncio.wait_for(websocket.receive_text(), timeout=15)
        auth = json.loads(auth)
        token = auth.get("token")
        user = None
        if token:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
            user = payload.get("sub")
        if not user:
            user = auth.get("user_id", f"guest_{os.urandom(3).hex()}")
        manager.web_clients[user] = websocket
        await websocket.send_text(json.dumps({"type": "auth_success", "user_id": user}))
        while True:
            msg = json.loads(await websocket.receive_text())
            msg["user_id"] = user
            await manager.send_to_worker(json.dumps(msg))
    except Exception as e:
        log(f"ws/web error: {e}")
    finally:
        manager.web_clients.pop(user, None)

@app.websocket("/ws/worker")
async def ws_worker(websocket: WebSocket):
    await websocket.accept()
    try:
        auth = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        auth = json.loads(auth)
        if not WORKER_SECRET_KEY or auth.get("secret") == WORKER_SECRET_KEY:
            manager.worker = websocket
            log("🤖 Worker authenticated.")
            while True:
                msg = await websocket.receive_text()
                data = json.loads(msg)
                uid = data.get("user_id")
                if uid in manager.web_clients:
                    await manager.web_clients[uid].send_text(msg)
        else:
            await websocket.close(code=1008, reason="Invalid key")
    except Exception as e:
        log(f"ws/worker error: {e}")
    finally:
        manager.worker = None

# === MAIN ===
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=10000)
