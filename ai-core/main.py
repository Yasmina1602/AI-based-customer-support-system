from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db, init_db, ChatMessage
from rag_engine import get_answer, load_data_to_chroma
import os

app = FastAPI(title="AI Sales Assistant API")

class MessageRequest(BaseModel):
    user_id: str
    message: str

class MessageResponse(BaseModel):
    response: str

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

@app.on_event("startup")
def on_startup():
    init_db()
    load_data_to_chroma(DATA_DIR)

@app.post("/reload-data")
def reload_data_endpoint():
    """data/ papkasidagi barcha .json fayllarni darhol qayta o'qitish (re-index) uchun API endpoint."""
    success = load_data_to_chroma(DATA_DIR, force_reload=True)
    if success:
        return {"status": "success", "message": "data/ papkasidagi barcha .json fayllar muvaffaqiyatli qayta o'qitildi!"}
    else:
        return {"status": "error", "message": "data/ papkasida .json fayllar topilmadi yoki yuklashda xatolik yuz berdi."}

@app.post("/chat", response_model=MessageResponse)
def chat_endpoint(request: MessageRequest, db: Session = Depends(get_db)):
    # 1. Save user message
    user_msg = ChatMessage(user_id=request.user_id, role="user", content=request.message)
    db.add(user_msg)
    db.commit()
    
    # 2. Get history (last 5 messages)
    history_records = db.query(ChatMessage).filter(ChatMessage.user_id == request.user_id).order_by(ChatMessage.timestamp.desc()).limit(5).all()
    history = [{"role": msg.role, "content": msg.content} for msg in reversed(history_records)]
    
    # 3. Get AI answer
    ai_response_text = get_answer(request.user_id, request.message, history)
    
    # 4. Save AI response
    ai_msg = ChatMessage(user_id=request.user_id, role="assistant", content=ai_response_text)
    db.add(ai_msg)
    db.commit()
    
    return MessageResponse(response=ai_response_text)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
