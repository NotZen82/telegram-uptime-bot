import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, CHECK_INTERVAL
from db import init_db, add_site, delete_site, get_user_sites, site_exists, delete_site_by_number
from checker import check_sites

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --------- COMMANDS ---------

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer(
        "👋 Uptime бот активен\n\n"
        "Команды:\n"
        "/add google.com — добавить сайт\n"
        "/list — список сайтов\n"
        "/status — краткий статус\n"
        "/remove 1 — удалить сайт"
    )

@dp.message(Command("add"))
async def add(msg: types.Message):
    try:
        url = msg.text.split(" ", 1)[1].strip().lower()

        if site_exists(url, msg.chat.id):
            await msg.answer(f"⚠️ Этот сайт уже есть в мониторинге: {url}")
            return

        add_site(url, msg.chat.id)
        await msg.answer(f"➕ Добавлено: {url}")

    except:
        await msg.answer("Используй: /add google.com")

@dp.message(Command("status"))
async def status_summary(msg: types.Message):
    sites = get_user_sites(msg.chat.id)

    if not sites:
        await msg.answer("📭 У тебя пока нет сайтов для мониторинга.")
        return

    up = 0
    down = 0
    unknown = 0

    for url, status in sites:
        if status == "UP":
            up += 1
        elif status == "DOWN":
            down += 1
        else:
            unknown += 1

    total = len(sites)

    await msg.answer(
        "📊 Статус мониторинга:\n\n"
        f"🟢 UP: {up}\n"
        f"🔴 DOWN: {down}\n"
        f"⚪ UNKNOWN: {unknown}\n"
        f"Всего: {total}"
    )


@dp.message(Command("remove"))
async def remove(msg: types.Message):
    try:
        value = msg.text.split(" ", 1)[1].strip()

        if value.isdigit():
            url = delete_site_by_number(msg.chat.id, int(value))

            if not url:
                await msg.answer("⚠️ Нет сайта с таким номером. Проверь /list")
                return

            await msg.answer(f"🗑 Удалено: {url}")
            return

        delete_site(value.lower(), msg.chat.id)
        await msg.answer(f"🗑 Удалено: {value.lower()}")

    except:
        await msg.answer("Используй: /remove 1 или /remove google.com")


# --------- BACKGROUND JOB ---------

async def scheduler_task():
    await check_sites(bot)


@dp.message(Command("list"))
async def list_sites(msg: types.Message):
    sites = get_user_sites(msg.chat.id)

    if not sites:
        await msg.answer("📭 У тебя пока нет сайтов для мониторинга.")
        return

    text = "📡 Твои сайты:\n\n"

    for i, site in enumerate(sites, start=1):
        text += f"{i}. {site[0]}\n"

    await msg.answer(text)
    

async def main():
    init_db()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduler_task, "interval", seconds=CHECK_INTERVAL)
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


@dp.message(Command("list"))
async def list_sites(msg: types.Message):
    sites = get_user_sites(msg.chat.id)

    if not sites:
        await msg.answer("📭 У тебя пока нет сайтов для мониторинга.")
        return

    text = "📡 Твои сайты:\n\n"

    for i, site in enumerate(sites, start=1):
        url, status = site

        if status == "UP":
            icon = "🟢"
        elif status == "DOWN":
            icon = "🔴"
        else:
            icon = "⚪"

        text += f"{i}. {icon} {url} — {status}\n"

    await msg.answer(text)


