import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
print(f"DEBUG: BOT_TOKEN o'qildi: {BOT_TOKEN[:10]}... (uzunligi: {len(BOT_TOKEN)})")
AI_CORE_URL = os.getenv("AI_CORE_URL", "http://127.0.0.1:8000")
