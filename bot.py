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
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, FSInputFile
)
from aiogram.client.default import DefaultBotProperties  # ← ЭТО НОВАЯ СТРОЧКА

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

logging.basicConfig(level=logging.INFO)

# ← ИЗМЕНЕНО: вот так теперь правильно
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
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

async def generate_image(prompt: str, image_bytes: Optional[bytes] = None) -> Optional[BytesIO]:
    img = Image.new('RGB', (512, 512), color=(random.randint(100, 255), random.randint(100, 255), random.randint(100, 255)))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except:
        font = ImageFont.load_default()
    short_prompt = (prompt[:50] + '...') if len(prompt) > 50 else prompt
    draw.text((10, 10), short_prompt, fill=(0, 0, 0), font=font)
    if image_bytes:
        try:
            orig_img = Image.open(BytesIO(image_bytes))
            orig_img.thumbnail((256, 256))
            img.paste(orig_img, (100, 100))
        except:
            pass
    bio = BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

# ← Остальной код полностью тот же (start_handler, profile, product, personal и т.д.)
# просто скопируй его из предыдущего сообщения — он не менялся

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

# … (вставь сюда все остальные обработчики из прошлого сообщения, они не менялись)

if __name__ == '__main__':
    print("Запуск бота...")
    asyncio.run(dp.start_polling(bot))
