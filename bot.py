import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, CHECK_INTERVAL
from db import init_db, add_site, delete_site
from checker import check_sites

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --------- COMMANDS ---------

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer(
        "👋 Uptime бот активен\n\n"
        "Команды:\n"
        "/add google.com\n"
        "/list (пока нет)\n"
        "/remove google.com"
    )


@dp.message(Command("add"))
async def add(msg: types.Message):
    try:
        url = msg.text.split(" ", 1)[1]
        add_site(url, msg.chat.id)
        await msg.answer(f"➕ Добавлено: {url}")
    except:
        await msg.answer("Используй: /add google.com")


@dp.message(Command("remove"))
async def remove(msg: types.Message):
    try:
        url = msg.text.split(" ", 1)[1]
        delete_site(url, msg.chat.id)
        await msg.answer(f"🗑 Удалено: {url}")
    except:
        await msg.answer("Используй: /remove google.com")


# --------- BACKGROUND JOB ---------

async def scheduler_task():
    await check_sites(bot)


async def main():
    init_db()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduler_task, "interval", seconds=CHECK_INTERVAL)
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())