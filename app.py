# File: server.py (Final Version with User Authentication)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException, Body
from fastapi.responses import FileResponse
import uvicorn
import json
import asyncio
import base64
import datetime
import bcrypt
import jwt
import os
from typing import Dict

# --- CONFIGURATION & SECURITY ---
# The SECRET_KEY is used to sign JWTs. It MUST be kept secret.
# For production, this is loaded from an environment variable.
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "a_very_secret_key_for_development_only")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # Token lasts for one day

USERS_DB_FILE = "users.json" # This file will store user credentials.

app = FastAPI()

# --- USER MANAGEMENT HELPERS ---
def load_users():
    """Loads users from the JSON file."""
    if not os.path.exists(USERS_DB_FILE):
        return {}
    with open(USERS_DB_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {} # Return empty dict if file is empty or corrupt

def save_users(users_data):
    """Saves the users dictionary to the JSON file."""
    with open(USERS_DB_FILE, "w") as f:
        json.dump(users_data, f, indent=4)

def get_password_hash(password):
    """Hashes a password for storing."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password, hashed_password):
    """Checks a plain password against a hashed one."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: datetime.timedelta | None = None):
    """Creates a new JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- END USER MANAGEMENT ---


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
    """Handles user registration."""
    username = user_data.get("username")
    password = user_data.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required.")
    
    users = load_users()
    if username in users:
        raise HTTPException(status_code=400, detail="Username already exists.")
    
    hashed_password = get_password_hash(password)
    users[username] = {"password": hashed_password}
    save_users(users)
    log_message(f"New user signed up: {username}")
    return {"message": "User created successfully."}

@app.post("/login")
async def login(user_data: dict = Body(...)):
    """Handles user login and issues a JWT."""
    username = user_data.get("username")
    password = user_data.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required.")

    users = load_users()
    user = users.get(username)
    if not user or not verify_password(password, user["password"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
        
    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": username}, expires_delta=access_token_expires
    )
    log_message(f"User logged in: {username}")
    return {"access_token": access_token, "token_type": "bearer"}

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

# --- WEBSOCKET ENDPOINTS ---

@app.websocket("/ws/worker")
async def worker_websocket(websocket: WebSocket):
    # This endpoint is simple as it's a trusted local connection
    await manager.connect_local_worker(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.forward_to_web_client(data)
    except WebSocketDisconnect:
        await manager.disconnect_local_worker()

@app.websocket("/ws/web")
async def web_client_websocket(websocket: WebSocket):
    user_id = None
    try:
        # First message must be authentication
        auth_data_str = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        auth_data = json.loads(auth_data_str)
        
        token = auth_data.get("token")
        
        # Determine user_id from token or use guest mode
        if token:
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                user_id = payload.get("sub")
                if user_id is None:
                    raise WebSocketDisconnect(code=1008, reason="Invalid token payload")
            except jwt.ExpiredSignatureError:
                raise WebSocketDisconnect(code=1008, reason="Token has expired")
            except jwt.InvalidTokenError:
                raise WebSocketDisconnect(code=1008, reason="Invalid token")
        else: # Guest Mode
            user_id = auth_data.get("user_id")
            if not user_id:
                raise WebSocketDisconnect(code=1008, reason="Guest user_id missing")

        # If authentication successful, connect client
        await manager.connect_web_client(websocket, user_id)
        
        while True:
            data_text = await websocket.receive_text()
            data = json.loads(data_text)
            
            if data.get("type") == "ping":
                continue
            
            # Re-assign user_id to ensure it's correct for every message
            data['user_id'] = user_id
            await manager.forward_to_worker(json.dumps(data))
            
    except WebSocketDisconnect:
        if user_id:
            manager.disconnect_web_client(user_id)
    except asyncio.TimeoutError:
        log_message("Client failed to authenticate in time.")
    except Exception as e:
        log_message(f"Error in web client websocket: {e}")
        if user_id:
            manager.disconnect_web_client(user_id)

