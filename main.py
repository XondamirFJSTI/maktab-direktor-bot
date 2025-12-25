import asyncio
import logging
import sys
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import aiosqlite 

# --- SOZLAMALAR ---
BOT_TOKEN = "8061768017:AAHVwaiJTd1vNDD7SlBd0CCCTixqu9AJHFc" 
ADMIN_ID = 2070459532 
DB_NAME = "school_db.sqlite"

# --- DATABASE LAYER ---
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE,
                full_name TEXT,
                phone TEXT,
                role TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS appeals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                category TEXT,
                message TEXT,
                created_at TIMESTAMP,
                status TEXT DEFAULT 'new'
            )
        ''')
        await db.commit()

async def add_user(telegram_id, full_name, phone, role):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (telegram_id, full_name, phone, role) VALUES (?, ?, ?, ?)",
            (telegram_id, full_name, phone, role)
        )
        await db.commit()

async def add_appeal(user_id, category, message):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO appeals (user_id, category, message, created_at) VALUES (?, ?, ?, ?)",
            (user_id, category, message, datetime.now())
        )
        await db.commit()

async def get_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM appeals") as cursor:
            count = await cursor.fetchone()
            return count[0]

# --- STATES ---
class AppealForm(StatesGroup):
    role = State()
    name = State()
    phone = State()
    category = State()
    message = State()

# --- KEYBOARDS ---
role_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👨‍👩‍👧‍👦 Ota-ona"), KeyboardButton(text="🎓 O'quvchi")],
        [KeyboardButton(text="👨‍🏫 O'qituvchi")]
    ], resize_keyboard=True
)

category_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💡 Taklif"), KeyboardButton(text="⚠️ Shikoyat")],
        [KeyboardButton(text="📝 Ariza"), KeyboardButton(text="⭐ Minnatdorchilik")]
    ], resize_keyboard=True
)

contact_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📞 Telefon raqamni yuborish", request_contact=True)]],
    resize_keyboard=True
)

# --- HANDLERS ---
router = Router()

@router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Assalomu alaykum, {html.bold(message.from_user.full_name)}!\n"
        "Buvayda Tumani 50- sonli maktab direktori qabulxonasiga xush kelibsiz.\n\n"
        "Iltimos, o'zingizni tanishtiring:",
        reply_markup=role_kb
    )
    await state.set_state(AppealForm.role)

@router.message(AppealForm.role)
async def process_role(message: Message, state: FSMContext):
    if message.text not in ["👨‍👩‍👧‍👦 Ota-ona", "🎓 O'quvchi", "👨‍🏫 O'qituvchi"]:
        await message.answer("Iltimos, tugmalardan birini tanlang.")
        return
    await state.update_data(role=message.text)
    await message.answer("To'liq ism-familiyangizni kiriting:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AppealForm.name)

@router.message(AppealForm.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Telefon raqamingizni yuboring yoki yozing (+998...):", reply_markup=contact_kb)
    await state.set_state(AppealForm.phone)

@router.message(AppealForm.phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text
    await state.update_data(phone=phone)
    await message.answer("Murojaat turini tanlang:", reply_markup=category_kb)
    await state.set_state(AppealForm.category)

@router.message(AppealForm.category)
async def process_category(message: Message, state: FSMContext):
    if message.text not in ["💡 Taklif", "⚠️ Shikoyat", "📝 Ariza", "⭐ Minnatdorchilik"]:
        await message.answer("Tugmalardan foydalaning.")
        return
    await state.update_data(category=message.text)
    await message.answer("Murojaatingiz matnini batafsil yozib qoldiring:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AppealForm.message)

@router.message(AppealForm.message)
async def process_message(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(message_text=message.text)
    data = await state.get_data()
    
    await add_user(message.from_user.id, data['name'], data['phone'], data['role'])
    await add_appeal(message.from_user.id, data['category'], data['message_text'])
    
    await message.answer("✅ Murojaatingiz qabul qilindi!")
    
    admin_text = (
        f"🔔 <b>Yangi murojaat!</b>\n\n"
        f"👤 <b>Kimdan:</b> {data['name']} ({data['role']})\n"
        f"📞 <b>Tel:</b> {data['phone']}\n"
        f"📂 <b>Kategoriya:</b> {data['category']}\n\n"
        f"💬 <b>Matn:</b>\n{data['message_text']}"
    )
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Adminga xabar bormadi: {e}")

    await state.clear()

@router.message(Command("stat"))
async def admin_stat(message: Message):
    if message.from_user.id == ADMIN_ID:
        count = await get_stats()
        await message.answer(f"📊 Jami murojaatlar soni: {count} ta")

async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    await init_db()
    dp.include_router(router)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exit")
