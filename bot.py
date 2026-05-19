import asyncio
from aiogram.types import FSInputFile

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, CHECK_INTERVAL

from db import (
    init_db,
    add_site,
    delete_site,
    get_user_sites,
    site_exists,
    delete_site_by_number,
    get_user_incidents,
)

from checker import check_sites
from monitor import check_many_sites, ssl_text, short_url


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def safe_answer(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass


async def safe_edit(message, text, reply_markup=None):
    try:
        await message.edit_text(
            text,
            reply_markup=reply_markup
        )
    except Exception as e:
        if "message is not modified" in str(e):
            return

        raise e


def main_menu():
    builder = InlineKeyboardBuilder()

    builder.button(text="📋 Список сайтов", callback_data="menu_list")
    builder.button(text="📊 Статус", callback_data="menu_status")
    builder.button(text="🔎 Проверить сейчас", callback_data="menu_check")
    builder.button(text="📉 Инциденты", callback_data="menu_incidents")
    builder.button(text="➕ Как добавить сайт", callback_data="menu_add_help")
    builder.button(text="❓ FAQ", callback_data="menu_faq")
    builder.button(text="🎧 Retro mode", callback_data="menu_retro")


    builder.adjust(1)
    return builder.as_markup()


def refresh_menu():
    builder = InlineKeyboardBuilder()

    builder.button(text="🔄 Обновить", callback_data="menu_check")
    builder.button(text="⬅️ Меню", callback_data="menu_back")

    builder.adjust(2)
    return builder.as_markup()


def sites_menu(sites):
    builder = InlineKeyboardBuilder()

    for i, _ in enumerate(sites, start=1):
        builder.button(
            text=f"🗑 Удалить {i}",
            callback_data=f"delete_site:{i}",
        )

    builder.button(text="⬅️ Назад", callback_data="menu_back")
    builder.adjust(2)

    return builder.as_markup()


def render_status_icon(status: str) -> str:
    if status == "UP":
        return "🟢"

    if status.startswith("HTTP 4"):
        return "🟠"

    if status == "UNKNOWN":
        return "⚪"

    return "🔴"


def build_status_text(sites):
    up = down = unknown = 0

    for _, status in sites:
        if status == "UP":
            up += 1
        elif status == "UNKNOWN":
            unknown += 1
        else:
            down += 1

    return (
        "📊 Статус мониторинга:\n\n"
        f"🟢 UP: {up}\n"
        f"🔴 DOWN/ERROR: {down}\n"
        f"⚪ UNKNOWN: {unknown}\n"
        f"Всего: {len(sites)}"
    )


def build_check_text(results):
    text = "🔎 Проверка сайтов:\n\n"

    for result in results:
        text += f"{result.icon} {short_url(result.url)} — {result.result}\n"

        ssl_info = ssl_text(result.ssl_days)

        if ssl_info:
            text += f"{ssl_info}\n"

        text += "\n"

    return text


def retro_menu():
    builder = InlineKeyboardBuilder()

    builder.button(text="🎮 Doom vibes", callback_data="retro:doom")
    builder.button(text="💾 Windows 95 mood", callback_data="retro:win95")
    builder.button(text="🕹 8-bit terminal", callback_data="retro:terminal")
    builder.button(text="📟 After midnightl", callback_data="retro:after-midnight")
    builder.button(text="⬅️ Меню", callback_data="menu_back")

    builder.adjust(1)
    return builder.as_markup()


# --------- COMMANDS ---------

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer(
        "👋 Uptime бот активен\n\n"
        "Выбери действие:",
        reply_markup=main_menu(),
    )


@dp.message(Command("add"))
async def add(msg: types.Message):
    try:
        url = msg.text.split(" ", 1)[1].strip().lower()

        if not url:
            raise ValueError

        if site_exists(url, msg.chat.id):
            await msg.answer(f"⚠️ Этот сайт уже есть в мониторинге: {url}")
            return

        add_site(url, msg.chat.id)
        await msg.answer(f"➕ Добавлено: {url}")

    except Exception:
        await msg.answer("Используй: /add google.com")


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

    except Exception:
        await msg.answer("Используй: /remove 1 или /remove google.com")


@dp.message(Command("list"))
async def list_sites(msg: types.Message):
    sites = get_user_sites(msg.chat.id)

    if not sites:
        await msg.answer("📭 У тебя пока нет сайтов для мониторинга.")
        return

    text = "📋 Твои сайты:\n\n"

    for i, (url, status) in enumerate(sites, start=1):
        icon = render_status_icon(status)
        text += f"{i}. {icon} {short_url(url)} — {status}\n"

    await msg.answer(text)


@dp.message(Command("status"))
async def status_summary(msg: types.Message):
    sites = get_user_sites(msg.chat.id)

    if not sites:
        await msg.answer("📭 У тебя пока нет сайтов для мониторинга.")
        return

    await msg.answer(build_status_text(sites))


@dp.message(Command("check"))
async def manual_check(msg: types.Message):
    sites = get_user_sites(msg.chat.id)

    if not sites:
        await msg.answer("📭 У тебя нет сайтов для проверки.")
        return

    await msg.answer("🔄 Проверяю сайты...")

    urls = [url for url, _ in sites]
    results = await check_many_sites(urls)

    await msg.answer(build_check_text(results))


@dp.message(Command("incidents"))
async def incidents(msg: types.Message):
    rows = get_user_incidents(msg.chat.id)

    if not rows:
        await msg.answer("📭 Инцидентов пока нет.")
        return

    text = "📉 Последние инциденты:\n\n"

    for url, status, created_at in rows:
        icon = "🟢" if status == "UP" else "🔴"
        text += f"{icon} {short_url(url)} — {status}\n"
        text += f"🕒 {created_at}\n\n"

    await msg.answer(text)


@dp.message(Command("retro"))
async def retro(msg: types.Message):
    await msg.answer(
        "🎧 Retro Monitoring Mode\n\n"
        "🎮 Doom vibes\n"
        "💾 Windows 95 mood\n"
        "🕹 8-bit terminal\n"
        "📟 Sysadmin after midnight\n\n"
        "Скоро тут будут MIDI-ссылки."
    )


# --------- CALLBACKS ---------

@dp.callback_query(F.data == "menu_back")
async def menu_back(callback: types.CallbackQuery):
    await safe_answer(callback)

    await callback.message.edit_text(
        "📡 Главное меню:",
        reply_markup=main_menu(),
    )


@dp.callback_query(F.data == "menu_add_help")
async def menu_add_help(callback: types.CallbackQuery):
    await safe_answer(callback)

    await callback.message.edit_text(
        "➕ Чтобы добавить сайт, напиши:\n\n"
        "/add google.com",
        reply_markup=main_menu(),
    )


@dp.callback_query(F.data == "menu_faq")
async def menu_faq(callback: types.CallbackQuery):
    await safe_answer(callback)

    text = (
        "❓ FAQ\n\n"
        "➕ Добавить сайт\n"
        "/add google.com\n\n"

        "📋 Список сайтов\n"
        "/list\n\n"

        "🗑 Удалить сайт\n"
        "/remove 1\n\n"

        "🟢 UP — сайт работает\n"
        "🟠 HTTP 4xx — предупреждение\n"
        "🔴 DOWN/ERROR — проблема\n\n"

        "🔐 SSL monitoring включён.\n"
        "Бот предупредит перед истечением сертификата.\n\n"

        "🎧 Retro mode\n"
        "/retro\n"
    )


@dp.callback_query(F.data == "menu_list")
async def menu_list(callback: types.CallbackQuery):
    await safe_answer(callback)

    sites = get_user_sites(callback.message.chat.id)

    if not sites:
        await callback.message.edit_text(
            "📭 У тебя пока нет сайтов.\n\n"
            "Добавь первый:\n/add google.com",
            reply_markup=main_menu(),
        )
        return

    text = "📋 Твои сайты:\n\n"

    for i, (url, status) in enumerate(sites, start=1):
        icon = render_status_icon(status)
        text += f"{i}. {icon} {short_url(url)} — {status}\n"

    await callback.message.edit_text(
        text,
        reply_markup=sites_menu(sites),
    )


@dp.callback_query(F.data == "menu_status")
async def menu_status(callback: types.CallbackQuery):
    await safe_answer(callback)

    sites = get_user_sites(callback.message.chat.id)

    if not sites:
        await callback.message.edit_text(
            "📭 У тебя пока нет сайтов.",
            reply_markup=main_menu(),
        )
        return

    await callback.message.edit_text(
        build_status_text(sites),
        reply_markup=main_menu(),
    )


@dp.callback_query(F.data == "menu_incidents")
async def menu_incidents(callback: types.CallbackQuery):
    await safe_answer(callback)

    rows = get_user_incidents(callback.message.chat.id)

    if not rows:
        await callback.message.edit_text(
            "📭 Инцидентов пока нет.",
            reply_markup=main_menu(),
        )
        return

    text = "📉 Последние инциденты:\n\n"

    for url, status, created_at in rows:
        icon = "🟢" if status == "UP" else "🔴"
        text += f"{icon} {short_url(url)} — {status}\n"
        text += f"🕒 {created_at}\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=main_menu(),
    )


@dp.callback_query(F.data.startswith("delete_site:"))
async def delete_site_callback(callback: types.CallbackQuery):
    await safe_answer(callback)

    number = int(callback.data.split(":")[1])

    url = delete_site_by_number(
        callback.message.chat.id,
        number,
    )

    if not url:
        await callback.message.edit_text(
            "⚠️ Сайт не найден. Обнови список.",
            reply_markup=main_menu(),
        )
        return

    await callback.message.edit_text(
        f"🗑 Удалено: {short_url(url)}",
        reply_markup=main_menu(),
    )


@dp.callback_query(F.data == "menu_check")
async def callback_check(callback: types.CallbackQuery):
    await safe_answer(callback)

    sites = get_user_sites(callback.message.chat.id)

    if not sites:
        await callback.message.edit_text(
            "📭 У тебя нет сайтов для проверки.",
            reply_markup=main_menu(),
        )
        return

    await callback.message.edit_text("🔄 Проверяю сайты...")

    urls = [url for url, _ in sites]
    results = await check_many_sites(urls)

    await callback.message.edit_text(
        build_check_text(results),
        reply_markup=refresh_menu(),
    )

def retro_menu():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="🎮 Doom vibes",
        callback_data="retro:doom"
    )

    builder.button(
        text="💾 Windows 95",
        callback_data="retro:windows95"
    )

    builder.button(
        text="🕹 Terminal",
        callback_data="retro:terminal"
    )

    builder.button(
        text="📟 After Midnight",
        callback_data="retro:after-midnight"
    )

    builder.button(
        text="⬅️ Меню",
        callback_data="menu_back"
    )

    builder.adjust(1)

    return builder.as_markup()


@dp.callback_query(F.data == "menu_retro")
async def menu_retro(callback: types.CallbackQuery):
    await safe_answer(callback)

    text = (
        "🎧 Retro Monitoring Mode\n\n"
        "Пока сайты проверяются — включи немного олдскульного вайба:\n\n"
        "🎮 Doom vibes\n"
        "💾 Windows 95 mood\n"
        "🕹 8-bit terminal\n"
        "📟 Sysadmin after midnight\n\n"
        "Выбери трек ниже и наслаждайся мониторингом."
    )

    await safe_edit(
        callback.message,
        text,
        reply_markup=retro_menu()
    )


@dp.callback_query(F.data.startswith("retro:"))
async def retro_track(callback: types.CallbackQuery):
    await safe_answer(callback)

    track = callback.data.split(":")[1]

    tracks = {
        "doom": ("music/doom.mid", "🎮 Doom vibes"),
        "windows95": ("music/windows95.mid", "💾 Windows 95"),
        "terminal": ("music/terminal.mid", "🕹 Terminal"),
        "after-midnight": ("music/after-midnight.mid", "📟 After Midnight"),
    }

    if track not in tracks:
        await callback.message.answer("Трек не найден.")
        return

    path, title = tracks[track]

    await callback.message.answer_document(
        FSInputFile(path),
        caption=f"{title}\n\n🎧 Retro Monitoring Mode"
    )


# --------- BACKGROUND JOB ---------

async def scheduler_task():
    await check_sites(bot)


async def main():
    init_db()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scheduler_task,
        "interval",
        seconds=CHECK_INTERVAL,
    )
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


