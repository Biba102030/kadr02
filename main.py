import asyncio
import logging
import os  # Добавляем импорт os для работы с файлами
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from keyboards import get_main_menu
from utils.parser import get_latest_articles, search_articles, fetch_article_content
from dotenv import load_dotenv
import json

# Импортируем новые модули (оставляем заглушки)
try:
    from news import fetch_news
except ImportError:
    async def fetch_news(lang="ru"):
        return [{"title": "Новость 1", "date": "2025-05-15", "url": "https://example.com"}]

try:
    from search import search as custom_search
except ImportError:
    async def custom_search(query, lang="ru"):
        return [{"title": f"Результат для {query}", "date": "2025-05-15", "url": "https://example.com"}]

try:
    from settings import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE, MAX_ARTICLES
except ImportError:
    SUPPORTED_LANGUAGES = ["ru", "uz"]
    DEFAULT_LANGUAGE = "ru"
    MAX_ARTICLES = 10

try:
    from user import UserManager
except ImportError:
    class UserManager:
        def __init__(self):
            self.users = {}
            self.load_users()

        def load_users(self):
            if os.path.exists("users.json"):
                with open("users.json", "r") as f:
                    self.users = json.load(f)

        def save_users(self):
            with open("users.json", "w") as f:
                json.dump(self.users, f, indent=4)

        def add_user(self, user_id, name, phone):
            self.users[user_id] = {"name": name, "phone": phone}
            self.save_users()

        def get_user(self, user_id):
            return self.users.get(user_id)

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

# Инициализация менеджера пользователей
user_manager = UserManager()

# Определение состояний для FSM
class AuthStates(StatesGroup):
    WAITING_FOR_NAME = State()
    WAITING_FOR_PHONE = State()

class SearchStates(StatesGroup):
    WAITING_FOR_QUERY = State()

# Хранилище последних статей
latest_articles = []

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    user = user_manager.get_user(user_id)
    if user:
        await message.answer(f"Добро пожаловать обратно, {user['name']}! Вы уже авторизованы.\nВыберите действие:", reply_markup=get_main_menu())
    else:
        await message.answer("Добро пожаловать! Пожалуйста, введите ваше имя:")
        await state.set_state(AuthStates.WAITING_FOR_NAME)

# Обработка имени
@dp.message(AuthStates.WAITING_FOR_NAME)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Спасибо! Теперь введите ваш номер телефона:")
    await state.set_state(AuthStates.WAITING_FOR_PHONE)

# Обработка номера телефона
@dp.message(AuthStates.WAITING_FOR_PHONE)
async def process_phone(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    data = await state.get_data()
    name = data.get("name")
    phone = message.text
    user_manager.add_user(user_id, name, phone)
    await message.answer(f"Спасибо, {name}! Вы успешно зарегистрированы.", reply_markup=get_main_menu())
    await state.clear()

# Обработка callback-запросов от кнопок
@dp.callback_query()
async def process_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    user = user_manager.get_user(user_id)
    if not user:
        await callback.message.answer("Пожалуйста, зарегистрируйтесь с помощью /start.")
        await callback.answer()
        return

    global latest_articles

    if callback.data == "kadrovik_latest":
        articles = await get_latest_articles(DEFAULT_LANGUAGE)
        if articles:
            latest_articles = articles[:MAX_ARTICLES]
            response = "📰 Последние статьи с Kadrovik.uz:\n\n"
            for i, article in enumerate(latest_articles, 1):
                response += f"{i}. {article['emoji']} *{article['title']}*\n📅 {article['date']}\n\n"
            
            buttons = [
                [types.InlineKeyboardButton(text=f"{i} Статья", callback_data=f"article_{i-1}")]
                for i in range(1, len(latest_articles) + 1)
            ]
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
            await callback.message.answer(response, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await callback.message.answer("Не удалось загрузить статьи. Попробуйте позже.")
    
    elif callback.data.startswith("article_"):
        article_index = int(callback.data.split("_")[1])
        if 0 <= article_index < len(latest_articles):
            article = latest_articles[article_index]
            content = await fetch_article_content(article['url'])
            if content:
                # Создаём текстовый файл с содержимым статьи
                filename = f"article_{article_index}.txt"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)
                
                # Отправляем файл
                with open(filename, "rb") as f:
                    await callback.message.answer_document(
                        document=f,
                        caption=f"📰 *{article['title']}*\n📅 {article['date']}",
                        parse_mode="Markdown"
                    )
                
                # Удаляем временный файл
                os.remove(filename)
            else:
                logging.warning(f"Не удалось загрузить содержимое статьи: {article['url']}")
                await callback.message.answer("Не удалось загрузить содержимое статьи.")
        else:
            await callback.message.answer("Статья не найдена.")

    elif callback.data == "kadrovik_search":
        await callback.message.answer("Введите запрос для поиска статей на Kadrovik.uz:")
        await state.set_state(SearchStates.WAITING_FOR_QUERY)
    elif callback.data == "help":
        await callback.message.answer("ℹ️ *Помощь*\n\n- Используйте /start для регистрации\n- Выберите действие из меню ниже")
    elif callback.data == "about":
        await callback.message.answer("🤖 *О боте*\n\nKadrovik Bot помогает вам получать актуальную информацию с сайта Kadrovik.uz. Вы можете просматривать последние статьи или искать материалы по ключевым словам.")
    elif callback.data == "kadrovik_news":
        news = await fetch_news(DEFAULT_LANGUAGE)
        if news:
            response = "🔔 Последние новости:\n\n"
            for item in news[:MAX_ARTICLES]:
                response += f"📢 *{item['title']}*\n📅 {item['date']}\n🔗 {item['url']}\n\n"
            await callback.message.answer(response, parse_mode="Markdown")
        else:
            await callback.message.answer("Не удалось загрузить новости. Попробуйте позже.")
    await callback.answer()

# Обработка поискового запроса
@dp.message(SearchStates.WAITING_FOR_QUERY)
async def process_search_query(message: types.Message, state: FSMContext):
    query = message.text
    articles = await search_articles(query, DEFAULT_LANGUAGE)
    if articles:
        response = f"📰 Результаты поиска по запросу '{query}':\n\n"
        for article in articles[:MAX_ARTICLES]:
            response += f"{article['emoji']} *{article['title']}*\n📅 {article['date']}\n🔗 {article['url']}\n\n"
        await message.answer(response, parse_mode="Markdown")
    else:
        custom_results = await custom_search(query, DEFAULT_LANGUAGE)
        if custom_results:
            response = f"📰 Результаты поиска (альтернативный метод) по запросу '{query}':\n\n"
            for result in custom_results[:MAX_ARTICLES]:
                response += f"📢 *{result['title']}*\n📅 {result['date']}\n🔗 {result['url']}\n\n"
            await message.answer(response, parse_mode="Markdown")
        else:
            await message.answer(f"По запросу '{query}' ничего не найдено.")
    await state.clear()

# Проверка авторизации
@dp.message()
async def check_authorization(message: types.Message):
    user_id = str(message.from_user.id)
    if not user_manager.get_user(user_id) and message.text != "/start":
        await message.answer("Пожалуйста, зарегистрируйтесь с помощью /start.")

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())