# File: app.py (Firebase Firestore Version - With Cloud Chat Storage)

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
from typing import Dict, List, Optional # <<< NEW: Added List and Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException, Body, Depends, Request # <<< NEW: Added Depends, Request
from fastapi.security import OAuth2PasswordBearer # <<< NEW: For JWT dependency
from fastapi.responses import FileResponse
from pydantic import BaseModel # <<< NEW: For data models
import uvicorn

# --- CONFIGURATION & SECURITY ---
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "a_very_secret_key_for_development_only")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 

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
    chats_collection = db.collection('chats') # <<< NEW: Collection for chats
    print("Successfully connected to Firebase Firestore.")

except Exception as e:
    print(f"FATAL: Could not initialize Firebase Admin SDK. Error: {e}")

# --- HELPER FUNCTION FOR JWT TOKEN CREATION ---
def create_access_token(data: dict, expires_delta: datetime.timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# <<< NEW: Dependency to get current user from JWT >>>
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login") # Points to your login route

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        # You could also check if the user still exists in the DB here if needed
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired", headers={"WWW-Authenticate": "Bearer"})
    except jwt.InvalidTokenError:
        raise credentials_exception
# <<< END NEW SECTION >>>

app = FastAPI()

# --- USER MANAGEMENT HELPERS ---
# (get_password_hash and verify_password remain the same)
def get_password_hash(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password, hashed_password):
    hashed_bytes = hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_bytes)

def log_message(msg):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")

class ConnectionManager:
    # (ConnectionManager class remains the same)
    def __init__(self):
        self.web_clients: dict[str, WebSocket] = {}
        self.local_worker: WebSocket | None = None

    async def connect_web_client(self, websocket: WebSocket, user_id: str):
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
            try:
                msg_data = json.loads(message)
                user_id = msg_data.get("user_id")
                if user_id and user_id in self.web_clients:
                    error_payload = {
                        "type": "error", "user_id": user_id,
                        "data": "AI worker is not connected. Please ensure the local worker.py script is running and connected."
                    }
                    await self.web_clients[user_id].send_text(json.dumps(error_payload))
            except Exception as e:
                log_message(f"Could not inform client about worker disconnect: {e}")

    async def forward_to_web_client(self, message: str):
        try:
            data = json.loads(message)
            msg_type = data.get("type", "unknown"); user_id = data.get("user_id")
            if msg_type == "ping": return
            if user_id and user_id in self.web_clients:
                await self.web_clients[user_id].send_text(message)
        except Exception as e:
            log_message(f"!!! CRITICAL ERROR in forward_to_web_client: {e}")

manager = ConnectionManager()

# --- HTTP ENDPOINTS ---

@app.get("/")
async def get_homepage():
    return FileResponse('index.html') 

@app.get("/status")
async def get_status():
    is_connected = manager.local_worker is not None and manager.local_worker.client_state.name == 'CONNECTED'
    return {"worker_connected": is_connected}

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

@app.post("/login")
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
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/upload/{user_id}")
# Note: This upload might need JWT protection too depending on requirements
async def http_upload_pdf(user_id: str, file: UploadFile = File(...)): 
    if not manager.local_worker: raise HTTPException(status_code=503, detail="Local AI worker is not connected.")
    content = await file.read(); content_base64 = base64.b64encode(content).decode('utf-8')
    CHUNK_SIZE = 512 * 1024
    await manager.forward_to_worker(json.dumps({ "type": "upload_start", "user_id": user_id, "filename": file.filename }))
    for i in range(0, len(content_base64), CHUNK_SIZE):
        await manager.forward_to_worker(json.dumps({ "type": "upload_chunk", "user_id": user_id, "data": content_base64[i:i + CHUNK_SIZE] }))
    await manager.forward_to_worker(json.dumps({ "type": "upload_end", "user_id": user_id }))
    return {"message": "File sent to worker for processing."}

# <<< NEW: Pydantic models for Chat data >>>
class ChatMessage(BaseModel):
    sender: str
    text: str
    imageB64: Optional[str] = None # Assuming image handling comes later

class ChatData(BaseModel):
    id: str # Client generates this (e.g., chat_timestamp)
    name: str
    type: str # 'pdf_chat' or 'ai_chat'
    timestamp: str # ISO format string
    history: List[ChatMessage]
    pdfName: Optional[str] = None

# <<< NEW: Chat History API Endpoints >>>
@app.post("/chats", status_code=201)
async def save_chat(chat_data: ChatData, current_user: str = Depends(get_current_user)):
    """Saves or updates a chat history for the logged-in user."""
    chat_id = chat_data.id
    # Store user ID along with chat data for ownership check
    chat_dict = chat_data.dict()
    chat_dict["userId"] = current_user 
    try:
        # Use chat_id as the document ID, associate with user
        chats_collection.document(f"{current_user}_{chat_id}").set(chat_dict)
        log_message(f"Chat saved/updated for user '{current_user}', chat ID: {chat_id}")
        return {"message": "Chat saved successfully", "chatId": chat_id}
    except Exception as e:
        log_message(f"Error saving chat for user '{current_user}': {e}")
        raise HTTPException(status_code=500, detail="Could not save chat history.")

@app.get("/chats")
async def list_chats(current_user: str = Depends(get_current_user)):
    """Lists metadata (id, name, timestamp) of chats for the logged-in user."""
    try:
        # Query chats where 'userId' field matches the current user
        user_chats_query = chats_collection.where('userId', '==', current_user).order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        
        chat_list = []
        for doc in user_chats_query:
            chat_data = doc.to_dict()
            chat_list.append({
                "id": chat_data.get("id"),
                "name": chat_data.get("name"),
                "timestamp": chat_data.get("timestamp"),
                "type": chat_data.get("type"),
                "pdfName": chat_data.get("pdfName") # Include pdfName if available
            })
        log_message(f"Retrieved {len(chat_list)} chats for user '{current_user}'")
        return chat_list
    except Exception as e:
        log_message(f"Error listing chats for user '{current_user}': {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve chat list.")

@app.get("/chats/{chat_id}")
async def get_chat_history(chat_id: str, current_user: str = Depends(get_current_user)):
    """Gets the full history of a specific chat for the logged-in user."""
    doc_id = f"{current_user}_{chat_id}" # Use the composite ID
    try:
        chat_doc_ref = chats_collection.document(doc_id)
        chat_doc = chat_doc_ref.get()
        if chat_doc.exists:
            log_message(f"Retrieved chat history for user '{current_user}', chat ID: {chat_id}")
            return chat_doc.to_dict()
        else:
            # Check if maybe the client sent the raw chat_id without prefix
            # This is less ideal but provides fallback
            legacy_doc_ref = chats_collection.document(chat_id)
            legacy_doc = legacy_doc_ref.get()
            if legacy_doc.exists and legacy_doc.to_dict().get("userId") == current_user:
                 log_message(f"Retrieved chat history (legacy ID) for user '{current_user}', chat ID: {chat_id}")
                 return legacy_doc.to_dict()
                 
            log_message(f"Chat not found or access denied for user '{current_user}', chat ID: {chat_id}")
            raise HTTPException(status_code=404, detail="Chat not found or you don't have permission.")
    except Exception as e:
        log_message(f"Error getting chat history for user '{current_user}', chat ID: {chat_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve chat history.")

@app.delete("/chats/{chat_id}", status_code=204)
async def delete_chat(chat_id: str, current_user: str = Depends(get_current_user)):
    """Deletes a specific chat for the logged-in user."""
    doc_id = f"{current_user}_{chat_id}"
    try:
        chat_doc_ref = chats_collection.document(doc_id)
        chat_doc = chat_doc_ref.get()
        if chat_doc.exists:
             # Ensure the userId matches - redundant but safe
            if chat_doc.to_dict().get("userId") == current_user:
                chat_doc_ref.delete()
                log_message(f"Deleted chat for user '{current_user}', chat ID: {chat_id}")
                return # FastAPI handles 204 No Content response
            else:
                 # This case should ideally not happen due to doc_id structure
                 raise HTTPException(status_code=403, detail="Permission denied.")
        else:
             # Try legacy ID delete
             legacy_doc_ref = chats_collection.document(chat_id)
             legacy_doc = legacy_doc_ref.get()
             if legacy_doc.exists and legacy_doc.to_dict().get("userId") == current_user:
                  legacy_doc_ref.delete()
                  log_message(f"Deleted chat (legacy ID) for user '{current_user}', chat ID: {chat_id}")
                  return
             
             log_message(f"Attempt to delete non-existent or unauthorized chat by user '{current_user}', chat ID: {chat_id}")
             raise HTTPException(status_code=404, detail="Chat not found or you don't have permission.")

    except Exception as e:
        log_message(f"Error deleting chat for user '{current_user}', chat ID: {chat_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not delete chat.")

# <<< END NEW SECTION >>>

# --- WEBSOCKET ENDPOINTS ---
# (Websocket endpoints remain the same)
@app.websocket("/ws/worker")
async def worker_websocket(websocket: WebSocket):
    await manager.connect_local_worker(websocket)
    try:
        while True: data = await websocket.receive_text(); await manager.forward_to_web_client(data)
    except WebSocketDisconnect: await manager.disconnect_local_worker()

@app.websocket("/ws/web")
async def web_client_websocket(websocket: WebSocket):
    user_id = None; await websocket.accept() 
    try:
        auth_data_str = await asyncio.wait_for(websocket.receive_text(), timeout=30)
        auth_data = json.loads(auth_data_str); token = auth_data.get("token")
        if token:
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                user_id = payload.get("sub")
                if user_id is None: await websocket.close(code=1008, reason="Invalid token payload"); return 
            except jwt.ExpiredSignatureError: await websocket.close(code=1008, reason="Token has expired"); return
            except jwt.InvalidTokenError: await websocket.close(code=1008, reason="Invalid token"); return
        else: # Guest Mode
            user_id = auth_data.get("user_id")
            if not user_id: await websocket.close(code=1008, reason="Guest user_id missing"); return
        await manager.connect_web_client(websocket, user_id)
        while True:
            data_text = await websocket.receive_text(); data = json.loads(data_text)
            if data.get("type") == "ping": continue
            data['user_id'] = user_id; await manager.forward_to_worker(json.dumps(data))
    except WebSocketDisconnect:
        if user_id: manager.disconnect_web_client(user_id)
    except asyncio.TimeoutError:
        log_message("Client failed to authenticate in time.")
        if websocket.client_state.name == 'CONNECTED': await websocket.close(code=1008, reason="Authentication timeout")
    except Exception as e:
        log_message(f"Error in web client websocket: {e}")
        if user_id and websocket.client_state.name == 'CONNECTED': manager.disconnect_web_client(user_id)

