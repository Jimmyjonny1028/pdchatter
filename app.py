# --- IMPORTS ---
import fitz
import time
from PIL import Image
import pytesseract
import os
from dotenv import load_dotenv
import google.generativeai as genai
import re
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from fastapi.responses import FileResponse

# --- 1. API CONFIGURATION ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found. Please set it as an environment variable on Render.")

genai.configure(api_key=GOOGLE_API_KEY)
print("Gemini API configured successfully.")

# --- 2. MODEL INITIALIZATION ---
print("Initializing Gemini model...")
llm_model_name = 'gemini-1.5-flash-latest' 
llm_model = genai.GenerativeModel(llm_model_name)
print("Gemini model initialized.")

# --- 3. FASTAPI APP SETUP ---
app = FastAPI()
document_state = { "full_text": None, "filename": None }

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

class Question(BaseModel):
    text: str

# --- 4. CORE LOGIC ---
def process_pdf(pdf_content: bytes, filename: str):
    global document_state
    print(f"Processing PDF: {filename}")
    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        full_text = "".join(page.get_text("text") for page in doc)

        if len(full_text.strip()) < 100:
            print("Scanned PDF detected, starting OCR...")
            full_text = ""
            for page_num, page in enumerate(doc):
                print(f"OCR on page {page_num + 1}/{len(doc)}")
                pix = page.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                full_text += pytesseract.image_to_string(img) + "\n"
        doc.close()

        if not full_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract any text from the PDF.")

        document_state["full_text"] = full_text
        document_state["filename"] = filename
        print("PDF processed successfully.")
        return {"message": f"Successfully processed '{filename}'. Ready to answer questions."}
    except Exception as e:
        print(f"Error processing PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 5. API ENDPOINTS ---
@app.get("/")
async def read_root():
    return FileResponse('index.html')

@app.post("/upload/")
async def upload_pdf(file: UploadFile = File(...)):
    content = await file.read()
    return process_pdf(content, file.filename)

@app.post("/ask/")
async def ask_question(question: Question):
    if document_state["full_text"] is None:
        raise HTTPException(status_code=400, detail="No PDF has been processed yet.")
    try:
        prompt = f"""
        You are a helpful and precise assistant...
        ---
        {document_state['full_text']}
        ---
        **User Question:**
        {question.text}
        **Answer:**
        """
        generation_config = genai.types.GenerationConfig(max_output_tokens=2048, temperature=0.25)
        response = llm_model.generate_content(prompt, generation_config=generation_config)
        answer = response.text.strip() if response.parts else "The model did not provide a response."
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
