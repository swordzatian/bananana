import asyncio
import logging
import os
import random
from io import BytesIO
from typing import Optional

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
from aiogram.webhook.aiohttp_server import setup_application  # ← ПРАВИЛЬНЫЙ ИМПОРТ
from aiohttp import web

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

users = {}

class States(StatesGroup):
    product_photo = State()
    personal_photo = State()

async def mock_generate(prompt: str, photo_bytes: Optional[bytes] = None) -> BytesIO:
    img = Image.new("RGB", (768, 768), color=(random.randint(80, 200), random.randint(80, 200), random.randint(80, 200)))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
    except:
        font = ImageFont.load_default()
    short_prompt = prompt[:60] + "..." if len(prompt) > 60 else prompt
    d.text((20, 20), short_prompt, fill="white", font=font)
    d.text((20, 740), "Nano Banana Pro Demo", fill="white", font=font)
    if photo_bytes:
        try:
            orig = Image.open(BytesIO(photo_bytes)).convert("RGB")
            orig.thumbnail((300, 300))
            img.paste(orig, (230, 200))
        except:
            pass
    bio = BytesIO()
    img.save(bio, "PNG")
    bio.seek(0)
    return bio

@router.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    if user_id not in users:
        users[user_id] = {"balance": 999, "refs": 0}
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мой профиль", callback_data="profile")],
        [InlineKeyboardButton(text="Карточка товара", callback_data="product")],
        [InlineKeyboardButton(text="Личная фотосессия", callback_data="personal")],
        [InlineKeyboardButton(text="Купить тариф", callback_data="tariff")],
    ])
    await message.answer("Добро пожаловать в демо Nano Banana Pro! Выберите опцию:", reply_markup=kb)

@router.callback_query(F.data == "profile")
async def profile(cb: CallbackQuery):
    user_id = cb.from_user.id
    u = users.get(user_id, {"balance": 0, "refs": 0})
    text = f"Профиль:\nID: {user_id}\nПодписка: free\nБаланс: {u['balance']} токенов\nРефералы: {u['refs']}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Реферальная программа", callback_data="referral")],
        [InlineKeyboardButton(text="Поддержка", callback_data="support")],
        [InlineKeyboardButton(text="Назад", callback_data="back")],
    ])
    await cb.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data == "back")
async def back(cb: CallbackQuery):
    await start(cb.message)

@router.callback_query(F.data == "referral")
async def referral(cb: CallbackQuery):
    username = (await bot.get_me()).username
    link = f"https://t.me/{username}?start={cb.from_user.id}"
    await cb.answer(f"Ваша реф-ссылка: {link}", show_alert=True)

@router.callback_query(F.data == "support")
async def support(cb: CallbackQuery):
    await cb.message.answer("Поддержка: @your_support (демо)")

@router.callback_query(F.data == "product")
async def product_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(States.product_photo)
    await cb.message.edit_text("Загрузите фото товара на светлом фоне.")

@router.message(States.product_photo, F.photo)
async def product_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    photo_bytes = await bot.download_file(file.file_path)
    await state.update_data(product_photo=photo_bytes.getvalue())
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="С инфографикой", callback_data="product_inf")],
        [InlineKeyboardButton(text="Без инфографики", callback_data="product_plain")],
    ])
    await message.answer("Выберите тип карточки:", reply_markup=kb)
    await state.set_state(States.product_photo)  # Остаёмся в state для генерации

@router.callback_query(F.data.startswith("product_"))
async def generate_product(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photo_bytes = data.get("product_photo")
    inf = "с инфографикой (заголовок, офферы, иконки)" if "inf" in cb.data else "без инфографики"
    prompt = f"Карточка товара {inf}: белый фон, стильный дизайн, описание, использование."
    img = await mock_generate(prompt, photo_bytes)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Редактировать промпт", callback_data="edit_product")],
        [InlineKeyboardButton(text="Перегенерировать", callback_data=cb.data)],
        [InlineKeyboardButton(text="Назад", callback_data="back")],
    ])
    await cb.message.answer_photo(FSInputFile(img, filename="product_card.png"), caption="Готовая карточка! (Демо)", reply_markup=kb)
    await state.clear()

@router.callback_query(F.data == "edit_product")
async def edit_product(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Редактируйте промпт: 'Карточка товара с инфографикой, заголовок Скидка 20%'")
    # Здесь можно добавить state для ввода текста, но для демо пропустим

@router.callback_query(F.data == "personal")
async def personal_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(States.personal_photo)
    await cb.message.edit_text("Пришлите фото лица + промпт (в подписи, напр. 'в деловом костюме').")

@router.message(States.personal_photo, F.photo)
async def personal_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    photo_bytes = await bot.download_file(file.file_path)
    prompt = message.caption or "Реалистичное фото человека в современном стиле."
    img = await mock_generate(prompt, photo_bytes.getvalue())
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Редактировать промпт", callback_data="edit_personal")],
        [InlineKeyboardButton(text="Фотосессия из 4 фото", callback_data="session_4")],
        [InlineKeyboardButton(text="Назад", callback_data="back")],
    ])
    await message.answer_photo(FSInputFile(img, filename="personal.jpg"), caption="Готово одно фото! (Демо)", reply_markup=kb)
    await state.update_data(prompt=prompt, photo=photo_bytes.getvalue())
    await state.set_state(States.personal_photo)

@router.callback_query(F.data == "session_4")
async def session_4(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prompt = data.get("prompt", "фото человека")
    photo_bytes = data.get("photo")
    for i, angle in enumerate(["спереди", "сбоку", "3/4", "сверху"]):
        angle_prompt = f"{prompt}, ракурс {angle}"
        img = await mock_generate(angle_prompt, photo_bytes)
        await cb.message.answer_photo(FSInputFile(img, filename=f"session_{i}.png"), caption=f"Ракурс {i+1} (Демо)")
    await state.clear()

@router.callback_query(F.data == "edit_personal")
async def edit_personal(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Редактируйте промпт: 'Фото в фотосессии, стиль минимализм'")

@router.callback_query(F.data == "tariff")
async def tariff(cb: CallbackQuery):
    text = "Тарифы (демо):\nBasic: 100 токенов/мес - 500 руб\nPro: 500 - 1500 руб\nUnlimited: без лимита - 3000 руб"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Basic", callback_data="buy_basic")],
        [InlineKeyboardButton(text="Pro", callback_data="buy_pro")],
        [InlineKeyboardButton(text="Unlimited", callback_data="buy_unlim")],
        [InlineKeyboardButton(text="Назад", callback_data="back")],
    ])
    await cb.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data.startswith("buy_"))
async def buy_tariff(cb: CallbackQuery):
    await cb.answer("Тариф куплен! Баланс +500 токенов (демо)")

@router.message(F.text == "/admin")
async def admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    text = f"Админка:\nЮзеры: {len(users)}\nГенераций сегодня: {random.randint(10, 100)}\nТоп-тариф: Pro"
    await message.answer(text)

async def on_startup(app):
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook"
    await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    print(f"Webhook установлен: {webhook_url}. Бот работает 24/7 без конфликтов!")

async def main():
    logging.basicConfig(level=logging.INFO)
    app = web.Application()
    setup_application(app, dp, bot=bot)  # ← ПРАВИЛЬНЫЙ SETUP
    app.router.add_get("/", lambda req: web.Response(text="Bot alive!"))  # Health check для Render

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Сервер запущен на порту {port}. Ожидание обновлений...")

    # Держим живым
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
