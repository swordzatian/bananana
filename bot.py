import asyncio
import logging
import os
import random
from io import BytesIO
from typing import Dict, Optional

from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    FSInputFile,
)
from aiogram.client.default import DefaultBotProperties  # ← КРИТИЧНО ДЛЯ 3.13+

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# ← ПРАВИЛЬНАЯ ИНИЦИАЛИЗАЦИЯ БОТА ДЛЯ aiogram ≥3.7
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# Простая память вместо БД (для демо)
users: Dict[int, Dict] = {}


class States(StatesGroup):
    product_photo = State()
    product_type = State()
    personal_photo = State()


async def mock_generate(prompt: str, photo_bytes: Optional[bytes] = None) -> BytesIO:
    img = Image.new("RGB", (768, 768), color=(
        random.randint(80, 200),
        random.randint(80, 200),
        random.randint(80, 200),
    ))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
    except:
        font = ImageFont.load_default()

    text = prompt[:70] + "..." if len(prompt) > 70 else prompt
    d.text((20, 20), text, fill="white", font=font)
    d.text((20, 680), "Nano Banana Pro Demo", fill="white", font=font)

    if photo_bytes:
        try:
            uploaded = Image.open(BytesIO(photo_bytes)).convert("RGB")
            uploaded.thumbnail((300, 300))
            img.paste(uploaded, (230, 200))
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
    await message.answer(
        "Привет! Это демо Nano Banana Pro\nВыбери функцию:", reply_markup=kb
    )


@router.callback_query(F.data == "profile")
async def profile(cb: CallbackQuery):
    u = users.get(cb.from_user.id, {"balance": 0, "refs": 0})
    text = f"ID: {cb.from_user.id}\nБаланс: {u['balance']} генераций\nРефералов: {u['refs']}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Реферальная ссылка", callback_data="ref")],
        [InlineKeyboardButton(text="Назад", callback_data="back")],
    ])
    await cb.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "back")
async def back(cb: CallbackQuery):
    await start(cb.message)


@router.callback_query(F.data == "ref")
async def ref_link(cb: CallbackQuery):
    username = (await bot.get_me()).username
    link = f"https://t.me/{username}?start={cb.from_user.id}"
    await cb.answer(link, show_alert=True)


@router.callback_query(F.data == "product")
async def product_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(States.product_photo)
    await cb.message.edit_text("Пришли фото товара на светлом фоне")


@router.message(States.product_photo, F.photo)
async def product_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.download_file_by_id(photo.file_id)
    await state.update_data(photo=file.read())

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="С инфографикой", callback_data="product_inf")],
        [InlineKeyboardButton(text="Без инфографики", callback_data="product_plain")],
    ])
    await message.answer("Выбери тип карточки:", reply_markup=kb)


@router.callback_query(F.data.in_(["product_inf", "product_plain"]))
async def product_generate(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photo_bytes = data.get("photo")

    inf = "с инфографикой" if cb.data == "product_inf" else "без инфографики"
    prompt = f"Профессиональная карточка товара {inf}, белый фон, яркие цвета, современный стиль"

    img = await mock_generate(prompt, photo_bytes)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ещё раз", callback_data=cb.data)],
        [InlineKeyboardButton(text="Назад", callback_data="back")],
    ])
    await cb.message.answer_photo(
        FSInputFile(img, filename="card.png"),
        caption="Готовая карточка! (демо-версия)",
        reply_markup=kb,
    )
    await state.clear()


@router.callback_query(F.data == "personal")
async def personal_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(States.personal_photo)
    await cb.message.edit_text("Пришли своё селфи + промпт (например: «в костюме на фоне моря»)")


@router.message(States.personal_photo, F.photo)
async def personal_generate(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.download_file_by_id(photo.file_id)
    prompt = message.caption or "реалистичное фото человека"

    img = await mock_generate(prompt, file.read())

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Фотосессия из 4 ракурсов", callback_data="session4")],
        [InlineKeyboardButton(text="Назад", callback_data="back")],
    ])
    await message.answer_photo(
        FSInputFile(img, filename="face.png"),
        caption="Одно фото готово!",
        reply_markup=kb,
    )
    await state.update_data(last_prompt=prompt, last_photo=file.read())


@router.callback_query(F.data == "session4")
async def session4(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prompt = data.get("last_prompt", "человек")
    photo = data.get("last_photo")

    for i, angle in enumerate(["спереди", "профиль", "3/4", "сзади"]):
        img = await mock_generate(f"{prompt}, ракурс {angle}", photo)
        await cb.message.answer_photo(FSInputFile(img, filename=f"angle_{i}.png"))

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="back")]])
    await cb.message.answer("Фотосессия готова!", reply_markup=kb)


@router.callback_query(F.data == "tariff")
async def tariff(cb: CallbackQuery):
    text = ("Тарифы:\n"
            "• Basic — 100 ген/мес — 490 ₽\n"
            "• Pro — 500 ген/мес — 1490 ₽\n"
            "• Unlimited — без лимита — 2990 ₽")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="back")]])
    await cb.message.edit_text(text, reply_markup=kb)


@router.message(F.text == "/admin")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(f"Админка\nПользователей: {len(users)}\nВсего генераций: {random.randint(50,200)}")


async def main():
    logging.basicConfig(level=logging.INFO)
    print("Бот запущен и работает 24/7")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
