import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
import aiohttp
from config import BOT_TOKEN, AI_CORE_URL

logging.basicConfig(level=logging.INFO)

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing in the environment variables.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def fetch_ai_response(user_id: str, message: str) -> str:
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{AI_CORE_URL}/chat"
            payload = {"user_id": str(user_id), "message": message}
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("response", "Kechirasiz, javob olishda xatolik yuz berdi.")
                else:
                    return f"Kechirasiz, server bilan ulanishda xatolik yuz berdi. Status: {response.status}"
        except Exception as e:
            logging.error(f"Error connecting to AI Core: {e}")
            return "Serverga ulanib bo'lmadi. Iltimos, AI Core ishlayotganligiga ishonch hosil qiling."

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Assalomu alaykum! Men AI Sotuvchi Assistentiman. Qanday yordam bera olaman?")

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    user_text = message.text
    
    # Send "typing..." action
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    # Request response from AI Core
    answer = await fetch_ai_response(user_id, user_text)
    
    await message.answer(answer)

async def main():
    print("Starting Telegram Bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
