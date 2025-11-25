import asyncio
import logging
import os
import random
import io
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
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, FSInputFile

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

users: Dict[int, Dict] = {}

class UserStates(StatesGroup):
    waiting_product_photo = State()
    choosing_card_type = State()
    editing_prompt = State()
    waiting_face_photos = State()
    editing_personal_prompt = State()

async def generate_image(prompt: str, image_path: Optional[str] = None) -> Optional[BytesIO]:
    img = Image.new('RGB', (512, 512), color=(random.randint(100, 255), random.randint(100, 255), random.randint(100, 255)))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    short_prompt = (prompt[:50] + '...') if len(prompt) > 50 else prompt
    draw.text((10, 10), short_prompt, fill=(0, 0, 0), font=font)
    if image_path:
        try:
            orig_img = Image.open(image_path)
            orig_img.thumbnail((256, 256))
            img.paste(orig_img, (100, 100))
        except:
            pass
    bio = BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in users:
        users[user_id] = {'sub': 'free', 'balance': 0, 'refs': 0}
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мой профиль", callback_data="profile")],
        [InlineKeyboardButton(text="Карточка товара", callback_data="product")],
        [InlineKeyboardButton(text="Личная фотосессия", callback_data="personal")],
        [InlineKeyboardButton(text="Купить тариф", callback_data="buy")]
    ])
    await message.answer("Добро пожаловать в демо Nano Banana Bot! Выберите опцию:", reply_markup=keyboard)

@router.callback_query(F.data == "profile")
async def profile_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    data = users.get(user_id, {'sub': 'free', 'balance': 0, 'refs': 0})
    text = f"Профиль:\nID: {user_id}\nПодписка: {data['sub']}\nБаланс: {data['balance']} токенов\nРефералы: {data['refs']}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Реферальная программа", callback_data="referral")],
        [InlineKeyboardButton(text="Поддержка", callback_data="support")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "product")
async def product_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_product_photo)
    await callback.message.edit_text("Загрузите фото товара на светлом фоне.")

@router.message(UserStates.waiting_product_photo, F.photo)
async def product_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    photo_bytes = io.BytesIO(await bot.download_file(file.file_path))
    photo_path = f"/tmp/product_{message.from_user.id}.jpg"
    Image.open(photo_bytes).save(photo_path)
    await state.update_data(product_photo=photo_path)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="С инфографикой", callback_data="infographic")],
        [InlineKeyboardButton(text="Без инфографики", callback_data="plain")]
    ])
    await message.answer("Выберите тип карточки:", reply_markup=keyboard)
    await state.set_state(UserStates.choosing_card_type)

@router.callback_query(UserStates.choosing_card_type)
async def choose_type(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photo_path = data['product_photo']
    infographic = callback.data == 'infographic'
    pre_prompt = "Анализируй фото: опиши товар, предложи фон белый, использование в быту."
    if infographic:
        pre_prompt += " Добавь инфографику: заголовок 'Скидка 20%', иконки доставки/гарантии, стиль минималистичный."
    await state.update_data(prompt=pre_prompt, infographic=infographic)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Редактировать промпт", callback_data="edit_prompt")],
        [InlineKeyboardButton(text="Начать генерацию", callback_data="generate_product")]
    ])
    await callback.message.edit_text(f"Предпромпт:\n{pre_prompt}\n\nРедактировать или генерировать?", reply_markup=keyboard)
    await state.set_state(UserStates.editing_prompt)

@router.callback_query(F.data == "generate_product")
async def generate_product(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prompt = data['prompt']
    photo_path = data['product_photo']
    img = await generate_image(prompt, photo_path)
    if img:
        await callback.message.answer_photo(FSInputFile(img, filename='product_card.png'), caption="Готовая карточка товара! (Демо-версия)")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Редактировать", callback_data="edit_prompt")],
        [InlineKeyboardButton(text="Перейти к фотосессии", callback_data="personal")],
        [InlineKeyboardButton(text="Перегенерировать", callback_data="generate_product")]
    ])
    await callback.message.answer("Готово! Что дальше?", reply_markup=keyboard)
    await state.clear()

@router.callback_query(F.data == "personal")
async def personal_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_face_photos)
    await callback.message.edit_text("Пришлите 1–3 фото лица + текст-промпт (например: 'в деловом костюме на фоне офиса').")

@router.message(UserStates.waiting_face_photos)
async def personal_photos(message: Message, state: FSMContext):
    if message.photo:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        photo_bytes = io.BytesIO(await bot.download_file(file.file_path))
        photo_path = f"/tmp/face_{message.from_user.id}.jpg"
        Image.open(photo_bytes).save(photo_path)
        prompt = message.caption or "Генерируй реалистичное фото на основе лица."
        await state.update_data(face_photo=photo_path, prompt=prompt)
        img = await generate_image(prompt, photo_path)
        if img:
            await message.answer_photo(FSInputFile(img, filename='personal.jpg'), caption="Одно фото готово! (Демо)")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Редактировать промпт", callback_data="edit_personal")],
            [InlineKeyboardButton(text="Фотосессия из 4 фото", callback_data="session_4")]
        ])
        await message.answer("Выберите:", reply_markup=keyboard)
        await state.set_state(UserStates.editing_personal_prompt)
    else:
        await message.answer("Пришлите фото!")

@router.callback_query(F.data == "session_4")
async def session_4(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    base_prompt = data['prompt']
    for i in range(4):
        angle_prompt = f"{base_prompt}, ракурс {['спереди', 'сбоку', 'сзади', 'сверху'][i]}"
        img = await generate_image(angle_prompt)
        if img:
            await callback.message.answer_photo(FSInputFile(img, filename=f'session_{i}.jpg'), caption=f"Ракурс {i+1} (Демо)")
    await state.clear()

@router.callback_query(F.data == "buy")
async def buy_handler(callback: CallbackQuery):
    text = "Тарифы (демо):\nBasic: 100 токенов/мес - 500 руб\nPro: 500 - 1500 руб\nUnlimited: без лимита - 3000 руб"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Basic", callback_data="buy_basic")],
        [InlineKeyboardButton(text="Pro", callback_data="buy_pro")],
        [InlineKeyboardButton(text="Unlimited", callback_data="buy_unlim")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.in_({"referral", "support"}))
async def referral_support(callback: CallbackQuery):
    if callback.data == "referral":
        bot_info = await bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"
        await callback.answer(f"Реф-ссылка: {link}", show_alert=True)
    else:
        await callback.message.answer("Поддержка: @your_support (демо)")

@router.message(F.text == "/admin")
async def admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    users_count = len(users)
    gens_today = random.randint(10, 50)
    text = f"Демо-статистика:\nЮзеры: {users_count}\nГенерации сегодня: {gens_today}"
    await message.answer(text)

@router.callback_query(F.data.startswith("edit_"))
async def edit_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Редактируй промпт в сообщении ниже.")
    await state.set_state(UserStates.editing_prompt if "prompt" in callback.data else UserStates.editing_personal_prompt)

if __name__ == '__main__':
    print("Запуск бота...")
    asyncio.run(dp.start_polling(bot))
