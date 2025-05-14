import asyncio
from aiogram import Bot, Dispatcher
from bot.handlers import start, search, news, settings

TOKEN = "YOUR_BOT_TOKEN"

async def main():
    bot = Bot(token=TOKEN, parse_mode="HTML")
    dp = Dispatcher()
    dp.include_router(start.router)
    dp.include_router(search.router)
    dp.include_router(news.router)
    dp.include_router(settings.router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
