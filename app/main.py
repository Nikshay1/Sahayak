from fastapi import FastAPI
from app.orchestrator import handle

print("🔥 app.main loaded")   # <-- MUST PRINT

app = FastAPI()

@app.post("/speak")
def speak_endpoint(payload: dict):
    text = payload.get("text")
    print("📥 Received text:", text)   # <-- ADD THIS
    handle(text)
    return {"status": "ok"}
