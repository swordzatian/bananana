import asyncio
import logging
import os
import random
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    Message, FSInputFile
)
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

users = {}

class Form(StatesGroup):
    waiting_photo = State()

# MOCK ГЕНЕРАЦИЯ — КРАСИВАЯ КАРТИНКА С ТВОИМ ФОТО
def generate_mock(prompt: str, photo_bytes: bytes = None) -> BytesIO:
    img = Image.new("RGB", (1024, 1024), (random.randint(30,100), random.randint(100,200), random.randint(150,255)))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((50, 50), "Nano Banana Pro", fill="white", font=font)
    draw.text((50, 150), prompt[:80], fill="white", font=font)
    draw.text((50, 950), "ДЕМО — РАБОТАЕТ 24/7", fill="yellow", font=font)
    if photo_bytes:
        try:
            face = Image.open(BytesIO(photo_bytes)).convert("RGB")
            face.thumbnail((400, 400))
            img.paste(face, (300, 400))
        except: pass
    bio = BytesIO()
    img.save(bio, "PNG")
    bio.seek(0)
    return bio

@router.message(CommandStart())
async def start(msg: Message):
    kb = [
        [InlineKeyboardButton(text="Мой профиль", callback_data="profile")],
        [InlineKeyboardButton(text="Карточка товара", callback_data="card")],
        [InlineKeyboardButton(text="Личная фотосессия", callback_data="face")],
        [InlineKeyboardButton(text="Купить тариф", callback_data="buy")]
    ]
    await msg.answer("🚀 Nano Banana Pro — демо готов!\nНажми кнопку:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data == "profile")
async def profile(cb: CallbackQuery):
    await cb.message.edit_text(f"👤 ID: {cb.from_user.id}\n💎 Подписка: Free\n⚡ Баланс: ∞ (демо)", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="back")]]))

@router.callback_query(F.data == "back")
async def back(cb: CallbackQuery):
    await start(cb.message)

@router.callback_query(F.data == "card")
async def card_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_photo)
    await cb.message.edit_text("📦 Пришли фото товара на светлом фоне")

@router.callback_query(F.data == "face")
async def face_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_photo)
    await cb.message.edit_text("🤳 Пришли своё селфи")

@router.message(Form.waiting_photo, F.photo)
async def photo_received(msg: Message, state: FSMContext):
    photo = msg.photo[-1]
    file = await bot.get_file(photo.file_id)
    downloaded = await bot.download_file(file.file_path)
    
    text = "Карточка товара с инфографикой" if "card" in msg.text.lower() else "Личная фотосессия"
    img = generate_mock(text, downloaded.read())
    
    await msg.answer_photo(FSInputFile(img, "result.png"), caption="Готово! (демо-версия)")
    await state.clear()

@router.callback_query(F.data == "buy")
async def buy(cb: CallbackQuery):
    await cb.message.edit_text("💳 Тарифы:\nBasic — 490₽\nPro — 1490₽\nUnlimited — 2990₽", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="back")]]))

@router.message(F.text == "/admin")
async def admin(msg: Message):
    if msg.from_user.id != ADMIN_ID: return
    await msg.answer("Админка активна\nПользователей: 1\nСтатус: онлайн")

# WEBHOOK — РАБОТАЕТ НА RENDER БЕЗ КОНФЛИКТОВ
async def main():
    logging.basicConfig(level=logging.INFO)
    
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
    
    # Автоустановка webhook
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook"
    await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    print(f"WEBHOOK УСТАНОВЛЕН: {webhook_url}")
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    await site.start()
    print("БОТ ЖИВОЙ 24/7")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
