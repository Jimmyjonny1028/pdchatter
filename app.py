# File: app.py (Fixed: supports ?token query-param, avoids UnboundLocalError, returns both token names)

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
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException, Body, Depends, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
import traceback

# --- CONFIGURATION & SECURITY ---
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "a_very_secret_key_for_development_only")
# Get worker secret key from environment variable
WORKER_SECRET_KEY = os.environ.get("WORKER_SECRET_KEY")
if not WORKER_SECRET_KEY:
    print("WARNING: WORKER_SECRET_KEY environment variable not set. Worker connections will be insecure (dev only).")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
WORKER_AUTH_TIMEOUT = 10  # Seconds to wait for worker auth message

# --- FIREBASE INITIALIZATION ---
try:
    encoded_key = os.environ.get("FIREBASE_SERVICE_ACCOUNT_BASE64")
    if not encoded_key:
        raise ValueError("FIREBASE_SERVICE_ACCOUNT_BASE64 environment variable not set.")

    decoded_key = base64.b64decode(encoded_key).decode('utf-8')
    service_account_info = json.loads(decoded_key)

    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    users_collection = db.collection('users')
    chats_collection = db.collection('chats')
    print("Successfully connected to Firebase Firestore.")

except Exception as e:
    print(f"FATAL: Could not initialize Firebase Admin SDK. Error: {e}")
    # In many deployments you may want to exit here:
    # exit(1)


# --- HELPER FUNCTION FOR JWT TOKEN CREATION ---
def create_access_token(data: dict, expires_delta: datetime.timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- Dependency to get current user from JWT ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired", headers={"WWW-Authenticate": "Bearer"})
    except jwt.InvalidTokenError:
        raise credentials_exception

app = FastAPI()

# --- USER MANAGEMENT HELPERS ---
def get_password_hash(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password, hashed_password):
    hashed_bytes = hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_bytes)

def log_message(msg):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")

class ConnectionManager:
    def __init__(self):
        self.web_clients: dict[str, WebSocket] = {}
        self.local_worker: WebSocket | None = None

    async def connect_web_client(self, websocket: WebSocket, user_id: str):
        # Accept handled in the endpoint now
        self.web_clients[user_id] = websocket
        log_message(f"Web client '{user_id}' connected.")

    async def connect_local_worker(self, websocket: WebSocket):
        self.local_worker = websocket
        log_message(">>> Local AI Worker Authenticated and Connected! <<<")

    def disconnect_web_client(self, user_id: str):
        if user_id in self.web_clients:
            try:
                del self.web_clients[user_id]
            except Exception:
                pass
        log_message(f"Web client '{user_id}' disconnected.")

    async def disconnect_local_worker(self):
        self.local_worker = None
        log_message(">>> Local AI Worker disconnected. <<<")

    async def forward_to_worker(self, message: str):
        if self.local_worker and self.local_worker.client_state.name == 'CONNECTED':
            try:
                await self.local_worker.send_text(message)
            except Exception as e:
                log_message(f"Error sending to worker: {e}")
        else:
            log_message("!!! ERROR: Worker not connected or authenticated. Cannot forward message. !!!")
            try:
                msg_data = json.loads(message)
                user_id = msg_data.get("user_id")
                if user_id and user_id in self.web_clients:
                    error_payload = {
                        "type": "error", "user_id": user_id,
                        "data": "AI worker is not connected or failed authentication. Please ensure the local worker.py script is running, has the correct key, and is connected."
                    }
                    await self.web_clients[user_id].send_text(json.dumps(error_payload))
            except Exception as e:
                log_message(f"Could not inform client about worker disconnect: {e}")

    async def forward_to_web_client(self, message: str):
        try:
            data = json.loads(message)
            msg_type = data.get("type", "unknown"); user_id = data.get("user_id")
            if msg_type == "ping": return # Ignore pings from worker
            if user_id and user_id in self.web_clients:
                await self.web_clients[user_id].send_text(message)
        except Exception as e:
            log_message(f"!!! CRITICAL ERROR in forward_to_web_client: {traceback.format_exc()}")

manager = ConnectionManager()

# --- Pydantic models for Chat data ---
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

# --- HTTP ENDPOINTS ---

@app.get("/")
async def get_homepage():
    return FileResponse('index.html')

@app.get("/status")
async def get_status():
    is_connected = manager.local_worker is not None and manager.local_worker.client_state.name == 'CONNECTED'
    return {"worker_connected": is_connected, "connected_web_clients": list(manager.web_clients.keys())}

@app.post("/signup")
async def signup(user_data: dict = Body(...)):
    username = user_data.get("username"); password = user_data.get("password")
    if not username or not password: raise HTTPException(status_code=400, detail="Username and password are required.")
    user_ref = users_collection.document(username)
    if user_ref.get().exists: raise HTTPException(status_code=400, detail="Username already exists.")
    hashed_password = get_password_hash(password)
    new_user_data = {"username": username, "password": hashed_password}
    try:
        users_collection.document(username).set(new_user_data)
        log_message(f"New user signed up: {username}")
        return {"message": "User created successfully."}
    except Exception as e:
        log_message(f"Error during signup: {e}")
        raise HTTPException(status_code=500, detail="Could not create user account.")

# Support /login, /auth/login and /token (alias)
@app.post("/login")
@app.post("/auth/login")
@app.post("/token")
async def login(user_data: dict = Body(...)):
    username = user_data.get("username"); password = user_data.get("password")
    if not username or not password: raise HTTPException(status_code=400, detail="Username and password are required.")
    user_ref = users_collection.document(username)
    user_doc = user_ref.get()
    if not user_doc.exists: raise HTTPException(status_code=401, detail="Incorrect username or password.")
    user_data_from_db = user_doc.to_dict()
    stored_password_hash = user_data_from_db.get("password")
    if not stored_password_hash or not verify_password(password, stored_password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": username}, expires_delta=access_token_expires)
    log_message(f"User logged in: {username}")
    # Return both names to maximize frontend compatibility
    return {"access_token": access_token, "token": access_token, "token_type": "bearer"}

@app.post("/upload/{user_id}")
async def http_upload_pdf(user_id: str, file: UploadFile = File(...)):
    if not manager.local_worker: raise HTTPException(status_code=503, detail="Local AI worker is not connected.")
    content = await file.read(); content_base64 = base64.b64encode(content).decode('utf-8')
    CHUNK_SIZE = 512 * 1024
    await manager.forward_to_worker(json.dumps({ "type": "upload_start", "user_id": user_id, "filename": file.filename }))
    for i in range(0, len(content_base64), CHUNK_SIZE):
        await manager.forward_to_worker(json.dumps({ "type": "upload_chunk", "user_id": user_id, "data": content_base64[i:i + CHUNK_SIZE] }))
    await manager.forward_to_worker(json.dumps({ "type": "upload_end", "user_id": user_id }))
    return {"message": "File sent to worker for processing."}

# --- Chat History API Endpoints ---
@app.post("/chats", status_code=201)
async def save_chat(chat_data: ChatData, current_user: str = Depends(get_current_user)):
    chat_id = chat_data.id
    chat_dict = chat_data.dict(); chat_dict["userId"] = current_user
    try:
        chats_collection.document(f"{current_user}_{chat_id}").set(chat_dict)
        log_message(f"Chat saved/updated for user '{current_user}', chat ID: {chat_id}")
        return {"message": "Chat saved successfully", "chatId": chat_id}
    except Exception as e:
        log_message(f"Error saving chat for user '{current_user}': {e}")
        raise HTTPException(status_code=500, detail="Could not save chat history.")

@app.get("/chats")
async def list_chats(current_user: str = Depends(get_current_user), type: Optional[str] = None):
    try:
        # Keep compatibility with query param ?type=...
        user_chats_query = chats_collection.where('userId', '==', current_user)
        # ordering - safe guard: only call order_by if the field exists in docs in your app
        user_chats_query = user_chats_query.order_by('timestamp', direction=firestore.Query.DESCENDING)
        chat_list = []
        for doc in user_chats_query.stream():
            chat_data = doc.to_dict()
            if chat_data and "id" in chat_data and "name" in chat_data:
                 chat_list.append({
                     "id": chat_data.get("id"), "name": chat_data.get("name"),
                     "timestamp": chat_data.get("timestamp"), "type": chat_data.get("type"),
                     "pdfName": chat_data.get("pdfName")
                 })
        log_message(f"Retrieved {len(chat_list)} chats for user '{current_user}' (type={type})")
        return chat_list
    except Exception as e:
        log_message(f"Error listing chats for user '{current_user}': {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Could not retrieve chat list.")

@app.get("/chats/{chat_id}")
async def get_chat_history(chat_id: str, current_user: str = Depends(get_current_user)):
    doc_id = f"{current_user}_{chat_id}"
    try:
        chat_doc_ref = chats_collection.document(doc_id); chat_doc = chat_doc_ref.get()
        if chat_doc.exists:
            log_message(f"Retrieved chat history for user '{current_user}', chat ID: {chat_id}")
            return chat_doc.to_dict()
        else:
             legacy_doc_ref = chats_collection.document(chat_id); legacy_doc = legacy_doc_ref.get()
             if legacy_doc.exists:
                  legacy_data = legacy_doc.to_dict()
                  if legacy_data and legacy_data.get("userId") == current_user:
                       log_message(f"Retrieved chat history (legacy ID) for user '{current_user}', chat ID: {chat_id}")
                       return legacy_data
             log_message(f"Chat not found or access denied for user '{current_user}', chat ID: {chat_id}")
             raise HTTPException(status_code=404, detail="Chat not found or you don't have permission.")
    except Exception as e:
        log_message(f"Error getting chat history for user '{current_user}', chat ID: {chat_id}: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Could not retrieve chat history.")

@app.delete("/chats/{chat_id}", status_code=204)
async def delete_chat(chat_id: str, current_user: str = Depends(get_current_user)):
    doc_id = f"{current_user}_{chat_id}"
    try:
        chat_doc_ref = chats_collection.document(doc_id); chat_doc = chat_doc_ref.get()
        if chat_doc.exists:
            chat_doc_ref.delete()
            log_message(f"Deleted chat for user '{current_user}', chat ID: {chat_id}")
            return
        else:
             legacy_doc_ref = chats_collection.document(chat_id); legacy_doc = legacy_doc_ref.get()
             if legacy_doc.exists:
                  legacy_data = legacy_doc.to_dict()
                  if legacy_data and legacy_data.get("userId") == current_user:
                       legacy_doc_ref.delete()
                       log_message(f"Deleted chat (legacy ID) for user '{current_user}', chat ID: {chat_id}")
                       return
             log_message(f"Attempt to delete non-existent/unauthorized chat by user '{current_user}', chat ID: {chat_id}")
             raise HTTPException(status_code=404, detail="Chat not found or you don't have permission.")
    except Exception as e:
        log_message(f"Error deleting chat for user '{current_user}', chat ID: {chat_id}: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Could not delete chat.")

# --- WEBSOCKET ENDPOINTS ---

# Worker endpoint with authentication
@app.websocket("/ws/worker")
async def worker_websocket(websocket: WebSocket):
    await websocket.accept()
    authenticated = False
    try:
        auth_data_str = await asyncio.wait_for(websocket.receive_text(), timeout=WORKER_AUTH_TIMEOUT)
        auth_data = json.loads(auth_data_str)

        if WORKER_SECRET_KEY:
            if auth_data.get("type") == "auth" and auth_data.get("secret") == WORKER_SECRET_KEY:
                authenticated = True
                await manager.connect_local_worker(websocket)
            else:
                log_message("!!! Worker connection attempt FAILED: Invalid or missing secret key. !!!")
                await websocket.close(code=1008, reason="Authentication failed")
                return
        else:
            authenticated = True
            log_message("WARNING: Worker connected without authentication (WORKER_SECRET_KEY not set).")
            await manager.connect_local_worker(websocket)

        if authenticated:
            while True:
                 data = await websocket.receive_text()
                 await manager.forward_to_web_client(data)

    except asyncio.TimeoutError:
        log_message(f"!!! Worker failed to authenticate within {WORKER_AUTH_TIMEOUT} seconds. Disconnecting. !!!")
        if websocket.client_state.name == 'CONNECTED':
            await websocket.close(code=1008, reason="Authentication timeout")
    except WebSocketDisconnect:
        if authenticated:
            await manager.disconnect_local_worker()
        else:
            log_message("Unauthenticated worker disconnected.")
    except json.JSONDecodeError:
         log_message("!!! Worker sent invalid JSON during authentication. Disconnecting. !!!")
         if websocket.client_state.name == 'CONNECTED':
            await websocket.close(code=1008, reason="Invalid authentication format")
    except Exception as e:
        log_message(f"!!! Error in worker websocket: {traceback.format_exc()} !!!")
        if authenticated and websocket.client_state.name == 'CONNECTED':
             await manager.disconnect_local_worker()

# Web client websocket — supports token in query string OR JSON first message
@app.websocket("/ws/web")
@app.websocket("/ws")
async def web_client_websocket(websocket: WebSocket):
    user_id = None
    await websocket.accept()
    try:
        # Try to read first message within 1s — if client used query param, they may not send.
        # Wait longer (30s) to allow clients that do send a JSON auth message.
        auth_data_str = None
        try:
            auth_data_str = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
        except asyncio.TimeoutError:
            # no immediate message — maybe client put token in query param; we'll try that below
            pass

        auth_data = {}
        if auth_data_str:
            try:
                auth_data = json.loads(auth_data_str)
            except Exception:
                # invalid JSON — we'll still try query param fallback
                auth_data = {}

        # Priority: message token, then query param token, then guest userid in message, then guest fallback.
        token = auth_data.get("token") or websocket.query_params.get("token")
        if token:
            try:
                payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
                user_id = payload.get("sub")
                if user_id is None:
                    await websocket.close(code=1008, reason="Invalid token payload"); return
            except jwt.ExpiredSignatureError:
                await websocket.close(code=1008, reason="Token has expired"); return
            except jwt.InvalidTokenError:
                await websocket.close(code=1008, reason="Invalid token"); return
        else:
            # If auth_data contains user_id (guest), use it
            user_id = auth_data.get("user_id") or websocket.query_params.get("user_id")
            if not user_id:
                # generate a guest id
                user_id = f"guest_{os.urandom(3).hex()}"

        # Connect the client *before* sending auth_success
        await manager.connect_web_client(websocket, user_id)

        # Send auth_success message back to the client
        await websocket.send_text(json.dumps({"type": "auth_success", "user_id": user_id}))

        # Message loop for authenticated web client
        while True:
            data_text = await websocket.receive_text(); data = json.loads(data_text)
            if data.get("type") == "ping": continue
            data['user_id'] = user_id
            await manager.forward_to_worker(json.dumps(data))

    except WebSocketDisconnect:
        if user_id: manager.disconnect_web_client(user_id)
        else: log_message("Web client disconnected before auth (no user_id)")
    except asyncio.TimeoutError:
        log_message("Client failed to authenticate in time.")
        if websocket.client_state.name == 'CONNECTED':
            await websocket.close(code=1008, reason="Authentication timeout")
    except json.JSONDecodeError:
         log_message("!!! Web client sent invalid JSON during authentication. Disconnecting. !!!")
         if websocket.client_state.name == 'CONNECTED':
            await websocket.close(code=1008, reason="Invalid authentication format")
    except Exception as e:
        log_message(f"Error in web client websocket: {traceback.format_exc()}")
        if user_id and websocket.client_state.name == 'CONNECTED': manager.disconnect_web_client(user_id)

# end of file

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
