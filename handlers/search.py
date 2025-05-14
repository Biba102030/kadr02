from aiogram import Router, types

router = Router()

@router.message(lambda msg: msg.text and not msg.text.startswith("/"))
async def search_handler(message: types.Message):
    await message.answer("🔍 Выполняется поиск... (здесь будет логика парсинга)")
