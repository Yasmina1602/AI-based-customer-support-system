import os
import sys
import traceback
from dotenv import load_dotenv

print("="*50)
print("1. .ENV VA SOZLAMALARNI TEKSHIRISH")
print("="*50)

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
print(f".env fayl manzili: {os.path.abspath(env_path)}")
print(f".env mavjudmi: {os.path.exists(env_path)}")

load_dotenv(env_path, override=True)

gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
print(f"O'qilgan GEMINI_API_KEY: '{gemini_key[:8]}...' (Uzunligi: {len(gemini_key)})")

if not gemini_key:
    print("XATOLIK: GEMINI_API_KEY bo'sh yoki topilmadi!")
elif not gemini_key.startswith("AIzaSy"):
    print(f"OGOHLANTIRISH: Kalit 'AIzaSy' bilan boshlanmayapti (hozirgi boshlanishi: '{gemini_key[:6]}')")
    print("Google AI Studio kalitlari odatda 'AIzaSy' bilan boshlanadi.")
else:
    print("Kalit formati to'g'ri ko'rinadi (AIzaSy bilan boshlanadi).")

print("\n" + "="*50)
print("2. CHROMADB TEKSHIRISH")
print("="*50)

try:
    import chromadb
    chroma_path = os.path.join(os.path.dirname(__file__), "chroma_db")
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_or_create_collection(name="ecommerce_faq")
    count = collection.count()
    print(f"ChromaDB muvaffaqiyatli ulandi!")
    print(f"Bazadagi hujjatlar (savol-javoblar) soni: {count}")

    test_query = "What payment methods do you accept?"
    print(f"\nSinov qidiruvi: '{test_query}'")
    results = collection.query(query_texts=[test_query], n_results=2)
    print("Topilgan kontekst:")
    if results['documents'] and results['documents'][0]:
        for idx, doc in enumerate(results['documents'][0]):
            print(f"--- Hujjat #{idx+1} ---")
            print(doc)
    else:
        print("Hech qanday ma'lumot topilmadi!")
except Exception as e:
    print(f"ChromaDB xatoligi yuz berdi:")
    traceback.print_exc()

print("\n" + "="*50)
print("3. GOOGLE GEMINI API TEKSHIRISH")
print("="*50)

try:
    import google.generativeai as genai
    # Transport 'rest' is often needed for newer Google AI Studio keys
    genai.configure(api_key=gemini_key, transport='rest')
    
    print("Mavjud modellar ro'yxati olinmoqda (list_models):")
    available_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f" - {m.name}")
                available_models.append(m.name)
    except Exception as e:
        print(f"Modellar ro'yxatini olishda xatolik: {e}")

    # Fallback model ro'yxati
    candidate_models = [
        'gemini-1.5-flash',
        'gemini-1.5-flash-latest',
        'gemini-1.5-flash-002',
        'gemini-1.5-flash-001',
        'gemini-1.5-pro',
        'gemini-1.5-pro-latest',
        'gemini-pro'
    ]
    
    # Agar list_models dan modellar chiqqan bo'lsa, ularni boshiga qo'shamiz
    if available_models:
        candidate_models = [m.replace("models/", "") for m in available_models] + candidate_models

    test_prompt = "Say hello in Uzbek."
    print(f"\nYuborilayotgan prompt: '{test_prompt}'")
    
    success = False
    for model_name in candidate_models:
        try:
            print(f"Sinab ko'rilmoqda: {model_name}...")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(test_prompt)
            print(f"✅ MUVAFFIQAYATLI! Model: {model_name}")
            print(f"Javob: {response.text}")
            success = True
            break
        except Exception as e:
            print(f"❌ {model_name} da xatolik: {e}")

    if not success:
        print("\nBarcha modellar sinab ko'rildi, lekin birortasi ham javob bermadi.")
except Exception as e:
    print("\n❌ GEMINI SOZLAMALARIDA XATOLIK:")
    traceback.print_exc()

except Exception as e:
    print("\n❌ GEMINI API XATOLIGI:")
    traceback.print_exc()

print("\n" + "="*50)
print("TEKSHIRUV YAKUNLANDI")
print("="*50)
