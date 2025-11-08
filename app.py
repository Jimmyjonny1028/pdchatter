# File: app.py - FIXED VERSION
import asyncio
import json
import base64
import datetime
import os
import bcrypt
import jwt
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body, Depends
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import uvicorn
import firebase_admin
from firebase_admin import credentials, firestore

# ---------------- CONFIG ----------------
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "a_very_secret_key_for_dev")
WORKER_SECRET_KEY = os.environ.get("WORKER_SECRET_KEY")
if not WORKER_SECRET_KEY:
    print("⚠️  Warning: WORKER_SECRET_KEY not set (dev only).")

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
ALGORITHM = "HS256"

# ---------------- FIREBASE INIT ----------------
try:
    encoded_key = os.environ.get("FIREBASE_SERVICE_ACCOUNT_BASE64")
    if not encoded_key:
        raise ValueError("FIREBASE_SERVICE_ACCOUNT_BASE64 not set")

    decoded_key = base64.b64decode(encoded_key).decode("utf-8")
    cred = credentials.Certificate(json.loads(decoded_key))
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    users_collection = db.collection("users")
    chats_collection = db.collection("chats")
    print("✅ Firebase initialized.")
except Exception as e:
    print(f"🔥 Firebase init failed: {e}")
    exit(1)

# ---------------- HELPERS ----------------
def create_access_token(data: dict, expires_delta: datetime.timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.timezone.utc) + (
        expires_delta or datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token.")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")

def get_password_hash(password): 
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain, hashed): 
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def log(msg): 
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

# ---------------- MODELS ----------------
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

# ---------------- CONNECTION MANAGER ----------------
class ConnectionManager:
    def __init__(self):
        self.web_clients = {}  # user_id -> websocket
        self.local_worker = None

    async def connect_web(self, ws: WebSocket, user: str):
        self.web_clients[user] = ws
        log(f"🌐 Web client {user} connected")

    async def connect_worker(self, ws: WebSocket):
        self.local_worker = ws
        log("🤖 Worker connected and authenticated")

    async def disconnect_worker(self):
        self.local_worker = None
        log("❌ Worker disconnected")

    def disconnect_web(self, user: str):
        if user in self.web_clients:
            del self.web_clients[user]
        log(f"🧑‍💻 Web client {user} disconnected")

    async def send_to_worker(self, msg: str):
        if self.local_worker:
            try:
                await self.local_worker.send_text(msg)
            except Exception as e:
                log(f"Error sending to worker: {e}")
        else:
            log("⚠️  No worker connected")

    async def send_to_client(self, msg: str):
        try:
            data = json.loads(msg)
            user = data.get("user_id")
            if user and user in self.web_clients:
                await self.web_clients[user].send_text(msg)
        except Exception as e:
            log(f"Error sending to client: {e}")

manager = ConnectionManager()
app = FastAPI()

# ---------------- ROUTES ----------------
@app.get("/")
async def index():
    return FileResponse("index.html")

@app.get("/status")
async def status():
    return {
        "worker_connected": manager.local_worker is not None,
        "clients": list(manager.web_clients.keys()),
    }

@app.post("/signup")
async def signup(data: dict = Body(...)):
    u, p = data.get("username"), data.get("password")
    if not u or not p: 
        raise HTTPException(400, "Missing credentials")
    ref = users_collection.document(u)
    if ref.get().exists: 
        raise HTTPException(400, "User exists")
    ref.set({"username": u, "password": get_password_hash(p)})
    log(f"New user: {u}")
    return {"message": "User created"}

@app.post("/login")
@app.post("/auth/login")
@app.post("/token")
async def login(data: dict = Body(...)):
    u, p = data.get("username"), data.get("password")
    ref = users_collection.document(u)
    doc = ref.get()
    if not doc.exists: 
        raise HTTPException(401, "Invalid login")
    if not verify_password(p, doc.to_dict().get("password")):
        raise HTTPException(401, "Invalid login")
    token = create_access_token({"sub": u})
    log(f"{u} logged in")
    return {"access_token": token, "token": token, "token_type": "bearer"}

@app.get("/chats")
async def get_chats(current_user: str = Depends(get_current_user)):
    chats = []
    for doc in chats_collection.where("userId", "==", current_user).stream():
        d = doc.to_dict()
        chats.append({
            "id": doc.id,  # Use Firestore document ID
            "name": d.get("name"),
            "timestamp": d.get("timestamp"),
            "type": d.get("type"),
            "pdfName": d.get("pdfName")
        })
    return chats

@app.get("/chats/{cid}")
async def get_chat(cid: str, current_user: str = Depends(get_current_user)):
    doc = chats_collection.document(cid).get()
    if not doc.exists:
        raise HTTPException(404, "Chat not found")
    d = doc.to_dict()
    
    # Verify ownership
    if d.get("userId") != current_user:
        raise HTTPException(403, "Forbidden")
    
    # Ensure history is always a list
    if "history" not in d or d["history"] is None:
        d["history"] = []
    
    d["id"] = doc.id
    return d

@app.post("/chats")
async def save_chat(chat: ChatData, current_user: str = Depends(get_current_user)):
    d = chat.dict()
    d["userId"] = current_user
    
    # Create new document with auto-generated ID
    doc_ref = chats_collection.document()
    d["id"] = doc_ref.id
    doc_ref.set(d)
    
    log(f"💾 Chat saved for {current_user} with ID {doc_ref.id}")
    return {"ok": True, "id": doc_ref.id}

@app.put("/chats/{cid}")
async def update_chat(cid: str, chat: ChatData, current_user: str = Depends(get_current_user)):
    doc_ref = chats_collection.document(cid)
    doc = doc_ref.get()
    
    if not doc.exists:
        raise HTTPException(404, "Chat not found")
    
    # Verify ownership
    if doc.to_dict().get("userId") != current_user:
        raise HTTPException(403, "Forbidden")
    
    d = chat.dict()
    d["userId"] = current_user
    d["id"] = cid
    doc_ref.set(d)
    
    log(f"💾 Chat updated for {current_user}")
    return {"ok": True, "id": cid}

@app.delete("/chats/{cid}")
async def delete_chat(cid: str, current_user: str = Depends(get_current_user)):
    doc_ref = chats_collection.document(cid)
    doc = doc_ref.get()
    
    if not doc.exists:
        raise HTTPException(404, "Chat not found")
    
    # Verify ownership
    if doc.to_dict().get("userId") != current_user:
        raise HTTPException(403, "Forbidden")
    
    doc_ref.delete()
    log(f"🗑️ Chat {cid} deleted for {current_user}")
    return {"ok": True}

# ---------------- WEBSOCKETS ----------------
@app.websocket("/ws/worker")
async def ws_worker(ws: WebSocket):
    await ws.accept()
    try:
        auth = json.loads(await ws.receive_text())
        if auth.get("type") != "auth" or auth.get("secret") != WORKER_SECRET_KEY:
            await ws.close(code=1008, reason="Auth failed")
            return
        await manager.connect_worker(ws)
        
        async for msg in ws.iter_text():
            await manager.send_to_client(msg)
    except WebSocketDisconnect:
        await manager.disconnect_worker()
    except Exception as e:
        log(f"Worker error: {e}")
        await manager.disconnect_worker()

@app.websocket("/ws")
@app.websocket("/ws/web")
async def ws_web(ws: WebSocket):
    await ws.accept()
    user = None
    try:
        # Try token in query first
        token = ws.query_params.get("token")
        guest_id = ws.query_params.get("guest_id")
        
        if token:
            try:
                payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
                user = payload.get("sub")
            except:
                pass
        
        if not user and guest_id:
            user = guest_id
        
        if not user:
            # Expect auth message
            msg = await ws.receive_text()
            d = json.loads(msg)
            if "token" in d:
                try:
                    payload = jwt.decode(d["token"], JWT_SECRET_KEY, algorithms=[ALGORITHM])
                    user = payload.get("sub")
                except:
                    pass
        
        if not user:
            user = f"guest_{os.urandom(3).hex()}"

        await manager.connect_web(ws, user)
        await ws.send_text(json.dumps({"type": "auth_success", "user_id": user}))

        async for msg in ws.iter_text():
            try:
                data = json.loads(msg)
                data["user_id"] = user
                await manager.send_to_worker(json.dumps(data))
            except Exception as e:
                log(f"Error processing message from {user}: {e}")
                
    except WebSocketDisconnect:
        manager.disconnect_web(user or "unknown")
    except Exception as e:
        log(f"Web client error: {e}")
        manager.disconnect_web(user or "unknown")

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
