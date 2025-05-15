import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from keyboards import get_main_menu
from utils.parser import get_latest_articles, search_articles
from dotenv import load_dotenv
import os
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env file")

# Инициализация бота
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# Определение состояний для FSM
class AuthStates(StatesGroup):
    WAITING_FOR_NAME = State()
    WAITING_FOR_PHONE = State()

class SearchStates(StatesGroup):
    WAITING_FOR_QUERY = State()

# Хранилище пользователей
users = {}

# Загрузка и сохранение пользователей
def load_users():
    global users
    if os.path.exists("users.json"):
        try:
            with open("users.json", "r") as f:
                users = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            users = {}
    else:
        users = {}
    logging.info(f"Загруженные пользователи: {users}")
    return users

def save_users():
    global users
    try:
        with open("users.json", "w") as f:
            json.dump(users, f, indent=4)
        logging.info(f"Сохранённые пользователи: {users}")
    except Exception as e:
        logging.error(f"Ошибка при сохранении пользователей: {e}")

# Загрузка пользователей при старте
load_users()

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if user_id in users:
        await message.answer(f"Добро пожаловать обратно, {users[user_id]['name']}! Вы уже авторизованы.\nВыберите действие:", reply_markup=get_main_menu())
    else:
        await message.answer("Добро пожаловать! Пожалуйста, введите ваше имя:")
        await state.set_state(AuthStates.WAITING_FOR_NAME)

# Обработка имени
@dp.message(AuthStates.WAITING_FOR_NAME)
async def process_name(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    users[user_id] = {"name": message.text}
    await message.answer("Спасибо! Теперь введите ваш номер телефона:")
    await state.set_state(AuthStates.WAITING_FOR_PHONE)

# Обработка номера телефона
@dp.message(AuthStates.WAITING_FOR_PHONE)
async def process_phone(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    users[user_id]["phone"] = message.text
    save_users()
    await message.answer(f"Спасибо, {users[user_id]['name']}! Вы успешно зарегистрированы.", reply_markup=get_main_menu())
    await state.clear()

# Обработка callback-запросов от кнопок
@dp.callback_query()
async def process_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    if user_id not in users:
        await callback.message.answer("Пожалуйста, зарегистрируйтесь с помощью /start.")
        await callback.answer()
        return

    if callback.data == "kadrovik_latest":
        articles = await get_latest_articles("ru")
        if articles:
            response = "📰 Последние статьи с Kadrovik.uz:\n\n"
            for article in articles:
                response += f"{article['emoji']} *{article['title']}*\n📅 {article['date']}\n🔗 {article['url']}\n\n"
            await callback.message.answer(response, parse_mode="Markdown")
        else:
            await callback.message.answer("Не удалось загрузить статьи. Попробуйте позже.")
    elif callback.data == "kadrovik_search":
        await callback.message.answer("Введите запрос для поиска статей на Kadrovik.uz:")
        await state.set_state(SearchStates.WAITING_FOR_QUERY)
    elif callback.data == "help":
        await callback.message.answer("ℹ️ *Помощь*\n\n- Используйте /start для регистрации\n- Выберите действие из меню ниже")
    elif callback.data == "about":
        await callback.message.answer("🤖 *О боте*\n\nKadrovik Bot помогает вам получать актуальную информацию с сайта Kadrovik.uz. Вы можете просматривать последние статьи или искать материалы по ключевым словам.")
    await callback.answer()

# Обработка поискового запроса
@dp.message(SearchStates.WAITING_FOR_QUERY)
async def process_search_query(message: types.Message, state: FSMContext):
    query = message.text
    articles = await search_articles(query, "ru")
    if articles:
        response = f"📰 Результаты поиска по запросу '{query}':\n\n"
        for article in articles:
            response += f"{article['emoji']} *{article['title']}*\n📅 {article['date']}\n🔗 {article['url']}\n\n"
        await message.answer(response, parse_mode="Markdown")
    else:
        await message.answer(f"По запросу '{query}' ничего не найдено.")
    await state.clear()

# Проверка авторизации для всех сообщений
@dp.message()
async def check_authorization(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id not in users and message.text != "/start":
        await message.answer("Пожалуйста, зарегистрируйтесь с помощью /start.")

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())