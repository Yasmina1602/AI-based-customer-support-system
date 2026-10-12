import os
import chromadb
import google.generativeai as genai
import json
import hashlib
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
if GEMINI_API_KEY:
    print(f"GEMINI_API_KEY yuklandi: {GEMINI_API_KEY[:6]}... (uzunligi: {len(GEMINI_API_KEY)})")
    genai.configure(api_key=GEMINI_API_KEY, transport='rest')
else:
    print("WARNING: GEMINI_API_KEY topilmadi yoki bo'sh!")

# Initialize ChromaDB
chroma_path = os.path.join(os.path.dirname(__file__), "chroma_db")
chroma_client = chromadb.PersistentClient(path=chroma_path)
collection = chroma_client.get_or_create_collection(name="ecommerce_faq")

# Fallback modellar ro'yxati (eng birinchi o'rinda sinovdan muvaffaqiyatli o'tgan gemini-flash-latest)
FALLBACK_MODELS = [
    'gemini-flash-latest',
    'gemini-1.5-flash',
    'gemini-1.5-flash-latest',
    'gemini-1.5-pro',
    'gemini-1.5-pro-latest',
    'gemini-pro'
]

def get_folder_or_file_hash(target_path: str) -> str:
    """Fayl yoki data papkasidagi barcha .json fayllarning umumiy xeshini hisoblaydi."""
    hasher = hashlib.md5()
    if os.path.isdir(target_path):
        json_files = sorted([f for f in os.listdir(target_path) if f.endswith(".json")])
        for filename in json_files:
            file_path = os.path.join(target_path, filename)
            hasher.update(filename.encode())
            with open(file_path, 'rb') as f:
                hasher.update(f.read())
    elif os.path.isfile(target_path):
        with open(target_path, 'rb') as f:
            hasher.update(f.read())
    return hasher.hexdigest()

def parse_faq_items(data):
    """Har xil formatdagi JSON fayllarni (list, dict, har xil kalitlar) avtomatik moslashtiradi."""
    items = []
    if isinstance(data, dict):
        for key in ['questions', 'data', 'faq', 'items']:
            if key in data and isinstance(data[key], list):
                items = data[key]
                break
        if not items and len(data.values()) == 1 and isinstance(list(data.values())[0], list):
            items = list(data.values())[0]
    elif isinstance(data, list):
        items = data
        
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        q = item.get('question') or item.get('q') or item.get('prompt') or item.get('query') or ''
        a = item.get('answer') or item.get('a') or item.get('response') or item.get('reply') or ''
        if q and a:
            normalized.append({"question": str(q).strip(), "answer": str(a).strip()})
            
    return normalized

def load_data_to_chroma(target_path: str, force_reload: bool = False):
    """
    Faqatgina ai-core/data papkasidagi barcha .json fayllarni avtomatik o'qitadi.
    Fayllar o'zgarsa yoki yangisi qo'shilsa avtomatik qayta indekslaydi.
    """
    global collection
    if not os.path.exists(target_path):
        print(f"Data papkasi/fayli topilmadi: {target_path}")
        return False
        
    hash_file_path = os.path.join(chroma_path, "dataset_hash.txt")
    current_hash = get_folder_or_file_hash(target_path)
    
    saved_hash = ""
    if os.path.exists(hash_file_path):
        with open(hash_file_path, "r", encoding="utf-8") as f:
            saved_hash = f.read().strip()
            
    # Agar fayllar o'zgargan bo'lsa yoki force_reload bo'lsa yoki baza bo'sh bo'lsa
    should_reload = force_reload or (current_hash != saved_hash) or (collection.count() == 0)
    
    if should_reload:
        print(f"🔄 Yangi ma'lumotlar aniqlandi! Qayta indekslash boshlandi ({target_path})...")
        try:
            # Fayllar ro'yxatini shakllantirish
            files_to_load = []
            if os.path.isdir(target_path):
                files_to_load = [os.path.join(target_path, f) for f in os.listdir(target_path) if f.endswith(".json")]
            elif os.path.isfile(target_path):
                files_to_load = [target_path]
                
            if not files_to_load:
                print("❌ data/ papkasida birorta ham .json fayl topilmadi!")
                return False
                
            all_faq_items = []
            for file_path in files_to_load:
                print(f"O'qilmoqda: {os.path.basename(file_path)}...")
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                items = parse_faq_items(data)
                all_faq_items.extend(items)
                
            if not all_faq_items:
                print("❌ JSON fayllardan savol-javoblar topilmadi.")
                return False
                
            # Eski kolleksiyani tozalash va yangilash
            try:
                chroma_client.delete_collection(name="ecommerce_faq")
            except Exception:
                pass
            collection = chroma_client.get_or_create_collection(name="ecommerce_faq")
            
            documents = []
            metadatas = []
            ids = []
            for i, item in enumerate(all_faq_items):
                documents.append(f"Q: {item['question']}\nA: {item['answer']}")
                metadatas.append(item)
                ids.append(f"doc_{i}")
                
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
            # Yangi hashni saqlaymiz
            with open(hash_file_path, "w", encoding="utf-8") as f:
                f.write(current_hash)
                
            print(f"✅ Muvaffaqiyatli yuklandi: {len(documents)} ta savol-javob ChromaDB ga kiritildi!")
            return True
        except Exception as e:
            print(f"❌ Datasetni yuklashda xatolik: {e}")
            return False
    else:
        print(f"Dataset o'zgarmagan ({collection.count()} ta savol-javob allaqachon tayyor).")
        return True

def get_answer(user_id: str, question: str, chat_history: list) -> str:
    """Gets answer using RAG and Gemini with automatic fallback."""
    # 1. Search in ChromaDB
    try:
        results = collection.query(
            query_texts=[question],
            n_results=2
        )
        
        context = ""
        if results['documents'] and results['documents'][0]:
            context = "\n\n".join(results['documents'][0])
    except Exception as e:
        print(f"ChromaDB query error: {e}")
        context = ""
        
    # 2. Prepare prompt for Gemini
    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
    
    prompt = f"""You are a helpful AI Sales Assistant for an ecommerce store.
Use the following context from our FAQ to answer the user's question. If the answer is not in the context, try to answer politely and helpfully.
Always reply in the language the user is speaking (default to Uzbek if unsure, or reply in the language they typed).

Context:
{context}

Chat History:
{history_text}

User Question: {question}
Answer:"""

    # 3. Model fallback loop
    global FALLBACK_MODELS
    for model_name in list(FALLBACK_MODELS):
        try:
            print(f"[AI] '{model_name}' bilan javob olinmoqda...")
            curr_model = genai.GenerativeModel(model_name)
            response = curr_model.generate_content(prompt)
            print(f"[AI] '{model_name}' muvaffaqiyatli javob qaytardi! ✅")
            
            # Agar boshqa model ishlagan bo'lsa, uni keyingi safar birinchi bo'lib tekshirish uchun boshiga o'tkazamiz
            if FALLBACK_MODELS[0] != model_name:
                FALLBACK_MODELS.remove(model_name)
                FALLBACK_MODELS.insert(0, model_name)
                
            return response.text
        except Exception as e:
            print(f"[AI] '{model_name}' da xatolik yoki limit: {e}. Keyingi modelga o'tilmoqda...")

    return "Kechirasiz, hozir barcha AI modellarida bandlik yoki cheklov bor. Iltimos, birozdan so'ng qayta urinib ko'ring."
