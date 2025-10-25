# File: worker.py (with enhanced logging)

import asyncio
import websockets
import json
import base64
import fitz
import numpy as np
from PIL import Image
import pytesseract
import re
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity
from typing import Dict
import datetime

# --- CONFIGURATION ---
RENDER_SERVER_URL = "wss://chatpdf-server-shtq.onrender.com/ws/worker"

try:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except Exception:
    pass # Will print a more specific message if OCR is attempted

# --- OLLAMA CLIENT INITIALIZATION ---
client = OpenAI(base_url='http://localhost:11434/v1', api_key='ollama')
embedding_model_name = 'nomic-embed-text'
llm_model_name = 'gpt-oss:20b'

# --- STATE MANAGEMENT ---
user_document_states: Dict[str, dict] = {}

def log_message(msg):
    """Helper for timestamped logs."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")

# --- CORE AI LOGIC (Unchanged) ---
# ... (All the functions like get_embeddings, process_pdf_task, ask_question_task are the same)
def get_embeddings(texts: list[str], model: str) -> list[list[float]]:
    res = client.embeddings.create(input=texts, model=model)
    return [embedding.embedding for embedding in res.data]

async def send_message(websocket, message_dict: dict):
    message_str = json.dumps(message_dict)
    await websocket.send(message_str)

async def process_pdf_task(pdf_b64: str, user_id: str, filename: str, websocket):
    try:
        await send_message(websocket, {"type": "status", "user_id": user_id, "data": f"Processing '{filename}'..."})
        pdf_content = base64.b64decode(pdf_b64)
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        full_text = "".join(page.get_text("text") for page in doc)

        if len(full_text.strip()) < 100:
            log_message("Minimal text found, attempting OCR...")
            full_text = ""
            try:
                for i, page in enumerate(doc):
                    await send_message(websocket, {"type": "status", "user_id": user_id, "data": f"Performing OCR on page {i+1}/{len(doc)}..."})
                    pix = page.get_pixmap(dpi=300)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    full_text += pytesseract.image_to_string(img) + "\n"
            except Exception as ocr_error:
                log_message(f"OCR FAILED: {ocr_error}")
                raise ValueError(f"OCR process failed. Is Tesseract installed and in your PATH? Error: {ocr_error}")

        doc.close()
        paragraphs = re.split(r'\n\s*\n', full_text)
        chunks = [re.sub(r'\s+', ' ', p).strip() for p in paragraphs if len(p.strip()) > 20]
        if not chunks: raise ValueError("Could not extract any meaningful text from the PDF.")

        await send_message(websocket, {"type": "status", "user_id": user_id, "data": f"Creating embeddings for {len(chunks)} text chunks..."})
        all_embeddings = []
        for i in range(0, len(chunks), 50):
            all_embeddings.extend(get_embeddings(chunks[i:i+50], model=embedding_model_name))

        user_document_states[user_id]["text_chunks"] = chunks
        user_document_states[user_id]["chunk_embeddings"] = np.array(all_embeddings)
        log_message(f"Successfully processed PDF '{filename}' for user {user_id}")
        await send_message(websocket, {"type": "status", "user_id": user_id, "data": f"Ready for questions about '{filename}'."})
    except Exception as e:
        log_message(f"ERROR processing PDF for user {user_id}: {e}")
        await send_message(websocket, {"type": "error", "user_id": user_id, "data": f"Failed to process PDF: {e}"})

async def ask_question_task(question: str, user_id: str, websocket):
    try:
        if user_id not in user_document_states or "chunk_embeddings" not in user_document_states[user_id]:
            raise ValueError("No document has been processed for this session yet.")
        state = user_document_states[user_id]
        question_embedding = np.array(get_embeddings([question], model=embedding_model_name)[0]).reshape(1, -1)
        similarities = cosine_similarity(question_embedding, state["chunk_embeddings"])[0]
        top_indices = np.argsort(similarities)[-5:][::-1]
        context = "\n\n---\n\n".join([state["text_chunks"][i] for i in top_indices])
        system_prompt = "You are an expert assistant..." # (rest of prompt is the same)
        user_prompt = f"CONTEXT:\n{context}\n\nQUESTION:\n{question}\n\nANSWER:"
        stream = client.chat.completions.create(model=llm_model_name, messages=[...], stream=True)
        log_message(f"Streaming answer for user {user_id}...")
        for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            if token:
                await send_message(websocket, {"type": "answer_chunk", "user_id": user_id, "data": token})
        await send_message(websocket, {"type": "answer_end", "user_id": user_id})
        log_message(f"Finished streaming answer for user {user_id}.")
    except Exception as e:
        log_message(f"ERROR answering question for user {user_id}: {e}")
        await send_message(websocket, {"type": "error", "user_id": user_id, "data": f"An error occurred: {e}"})

# --- MAIN WEBSOCKET CONNECTION LOOP (MODIFIED WITH ENHANCED LOGGING) ---
async def main():
    while True:
        log_message(f"Attempting to connect to Render server at {RENDER_SERVER_URL}...")
        try:
            async with websockets.connect(
                RENDER_SERVER_URL,
                max_size=2**24,
                write_limit=2**24,
                ping_interval=20,
                ping_timeout=20
            ) as websocket:
                log_message(">>> Connection SUCCESSFUL. Waiting for tasks. <<<")
                while True:
                    message_str = await websocket.recv()
                    message = json.loads(message_str)
                    
                    user_id = message.get("user_id")
                    task_type = message.get("type")

                    log_message(f"Received task of type '{task_type}' for user '{user_id}'.")

                    if task_type == "upload_start":
                        if user_id not in user_document_states: user_document_states[user_id] = {}
                        user_document_states[user_id]['file_chunks'] = []
                        user_document_states[user_id]['filename'] = message.get("filename")
                    elif task_type == "upload_chunk":
                        if user_id in user_document_states:
                            user_document_states[user_id]['file_chunks'].append(message["data"])
                    elif task_type == "upload_end":
                        if user_id in user_document_states and 'file_chunks' in user_document_states[user_id]:
                            full_b64_data = "".join(user_document_states[user_id]['file_chunks'])
                            filename = user_document_states[user_id]['filename']
                            asyncio.create_task(process_pdf_task(full_b64_data, user_id, filename, websocket))
                            del user_document_states[user_id]['file_chunks']
                    elif task_type == "ask":
                        asyncio.create_task(ask_question_task(message["data"], user_id, websocket))

        except websockets.exceptions.ConnectionClosed as e:
            log_message(f"!!! Connection CLOSED: {e}. Retrying in 5 seconds... !!!")
            await asyncio.sleep(5)
        except ConnectionRefusedError:
            log_message("!!! Connection REFUSED. Is the Render server running? Retrying in 5 seconds... !!!")
            await asyncio.sleep(5)
        except Exception as e:
            log_message(f"!!! An unexpected error occurred: {e}. Retrying in 5 seconds... !!!")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
