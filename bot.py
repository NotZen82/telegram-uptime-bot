import asyncio
from pathlib import Path

from aiogram.types import FSInputFile

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, CHECK_INTERVAL, FAILURE_THRESHOLD

from db import (
    init_db,
    add_site,
    delete_site,
    get_user_sites,
    get_user_site_by_number,
    get_user_site_detail,
    site_exists,
    delete_site_by_number,
    get_user_incidents,
    get_last_site_incident,
    format_duration,
)

from checker import check_sites
from monitor import check_many_sites, ssl_text, short_url


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
BASE_DIR = Path(__file__).resolve().parent


TRACKS = {
    "beatles": (
        "music/Beatles_Yesterday.mid",
        "🎵 Beatles • Yesterday"
    ),
    "toto": (
        "music/Toto_Africa.mid",
        "🎵 Toto • Africa"
    ),
    "queen": (
        "music/Queen_Bohemian_Rhapsody.mid",
        "🎵 Queen • Bohemian Rhapsody"
    ),
    "rick": (
        "music/Rick_Astley_Never_Gonna_Give_You_Up.mid",
        "🎵 Rick Astley • Never Gonna Give You Up"
    ),
    "mermaid": (
        "music/Under_The_Sea_Little_Mermaid.mid",
        "🎵 Under The Sea • Little Mermaid"
    ),
    "pirates": (
        "music/Pirates_of_the_Caribbean_He's_a_Pirate.mid",
        "🎵 Pirates of the Caribbean • He's a Pirate"
    ),
    "jd": (
        "music/J.D._Souther_You're_Only_Lonely.mid",
        "🎵 J.D. Souther • You're Only Lonely"
    ),
    "pink": (
        "music/Pink_There_You_Go.mid",
        "🎵 Pink • There You Go"
    ),
    "beverly": (
        "music/Beverly_Hills_Cop _Axel_F.mid",
        "🎵 Beverly Hills Cop • Axel F"
    ),
    "eminem": (
        "music/Eminem_Welcome_2_Detroit.mid",
        "🎵 Eminem • Welcome 2 Detroit"
    ),
    "country": (
        "music/John_Denver_Country_roads.mid",
        "🎵 John Denver • Country Roads"
    ),
    "clash": (
        "music/The_Clash_Should_I_Stay_or_Should_I_Go.mid",
        "🎵 The Clash • Should I Stay or Should I Go"
    ),
}


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

        try:
            await message.edit_caption(
                caption=text,
                reply_markup=reply_markup
            )
        except Exception as caption_error:
            if "message is not modified" in str(caption_error):
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
    builder.button(text="🧹 Очистить чат", callback_data="menu_cleanup")


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
            text=f"ℹ️ Подробнее {i}",
            callback_data=f"site_detail:{i}",
        )
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


def site_card_menu(number):
    builder = InlineKeyboardBuilder()

    builder.button(text="🔄 Проверить", callback_data=f"site_detail:{number}")
    builder.button(text="🗑 Удалить", callback_data=f"delete_site:{number}")
    builder.button(text="📋 Список", callback_data="menu_list")
    builder.button(text="⬅️ Меню", callback_data="menu_back")

    builder.adjust(2)
    return builder.as_markup()


def format_incident_text(incident):
    if not incident:
        return "нет"

    status = incident["status"]
    created_at = incident["created_at"]

    if status == "RESOLVED":
        duration = format_duration(incident["duration_seconds"])
        return f"восстановлен, {created_at}, downtime {duration}"

    return f"{status}, {created_at}"


async def build_site_card(site, number=None):
    url = site["url"]
    status = site["status"]
    failure_count = site["failure_count"] or 0
    incident = get_last_site_incident(site["chat_id"], url)
    result = (await check_many_sites([url]))[0]

    ssl_info = ssl_text(result.ssl_days) or "нет данных"
    status_icon = render_status_icon(status)

    title = f"🌐 {short_url(url)}"
    if number:
        title = f"{number}. {title}"

    return (
        f"{title}\n\n"
        f"Статус в базе: {status_icon} {status}\n"
        f"Проверка сейчас: {result.icon} {result.result}\n"
        f"SSL: {ssl_info}\n"
        f"Ошибок подряд: {failure_count}/{FAILURE_THRESHOLD}\n"
        f"Последний инцидент: {format_incident_text(incident)}"
    )


def retro_menu():
    builder = InlineKeyboardBuilder()

    for key, (_, title) in TRACKS.items():
        builder.button(
            text=title,
            callback_data=f"retro:{key}"
        )

    builder.button(
        text="⬅️ Меню",
        callback_data="menu_back"
    )

    builder.adjust(1)

    return builder.as_markup()

def after_track_menu():
    builder = InlineKeyboardBuilder()

    builder.button(text="🧹 Очистить чат", callback_data="menu_cleanup")
    builder.button(text="⬅️ Меню", callback_data="menu_back")

    builder.adjust(2)
    return builder.as_markup()


def cleanup_confirm_menu():
    builder = InlineKeyboardBuilder()

    builder.button(text="OK", callback_data="cleanup_confirm")
    builder.button(text="⬅️ Меню", callback_data="menu_back")

    builder.adjust(2)
    return builder.as_markup()


# --------- COMMANDS ---------

@dp.message(Command("start"))
async def start(msg: types.Message):
    chat_id = msg.chat.id
    current_message_id = msg.message_id

    for msg_id in range(current_message_id, current_message_id - 100, -1):
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception:
            pass

    await bot.send_message(
        chat_id,
        "📡 Главное меню:",
        reply_markup=main_menu()
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


@dp.message(Command("site"))
async def site_card(msg: types.Message):
    sites = get_user_sites(msg.chat.id)

    if not sites:
        await msg.answer("📭 У тебя пока нет сайтов для мониторинга.")
        return

    try:
        value = msg.text.split(" ", 1)[1].strip().lower()
    except Exception:
        text = "🌐 Выбери сайт:\n\n"

        for i, (url, status) in enumerate(sites, start=1):
            icon = render_status_icon(status)
            text += f"{i}. {icon} {short_url(url)} — {status}\n"

        await msg.answer(
            text,
            reply_markup=sites_menu(sites),
        )
        return

    if value.isdigit():
        number = int(value)
        site = get_user_site_by_number(msg.chat.id, number)
    else:
        number = None
        site = get_user_site_detail(msg.chat.id, value)

    if not site:
        await msg.answer("⚠️ Сайт не найден. Проверь /list")
        return

    text = await build_site_card(site, number=number)

    await msg.answer(
        text,
        reply_markup=site_card_menu(number) if number else main_menu(),
    )


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
        if status == "RESOLVED":
            icon = "🟢"
            status_text = "восстановлен"
        elif status == "UP":
            icon = "🟢"
            status_text = "UP"
        else:
            icon = "🔴"
            status_text = status

        text += f"{icon} {short_url(url)} — {status_text}\n"
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

    await safe_edit(
        callback.message,
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
        "🌐 Карточка сайта\n"
        "/site 1\n\n"
        "🗑 Удалить сайт\n"
        "/remove 1\n\n"
        "🟢 UP — работает\n"
        "🟠 HTTP 4xx — предупреждение\n"
        "🔴 DOWN — недоступен\n\n"
        "🔐 SSL monitoring включён.\n"
        "Бот предупредит перед истечением сертификата.\n\n"
        "🎧 Retro mode — oldschool MIDI vibes"
    )

    await safe_edit(
        callback.message,
        text,
        reply_markup=main_menu()
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
        await safe_edit(
            callback.message,
            "📭 Инцидентов пока нет.",
            reply_markup=main_menu()
        )
        return

    text = "📉 Последние инциденты:\n\n"

    for url, status, created_at in rows:
        if status == "RESOLVED":
            icon = "🟢"
            status_text = "восстановлен"
        elif status == "UP":
            icon = "🟢"
            status_text = "UP"
        else:
            icon = "🔴"
            status_text = status

        text += f"{icon} {short_url(url)} — {status_text}\n"
        text += f"🕒 {created_at}\n\n"

    await safe_edit(
        callback.message,
        text,
        reply_markup=main_menu()
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


@dp.callback_query(F.data.startswith("site_detail:"))
async def site_detail_callback(callback: types.CallbackQuery):
    await safe_answer(callback)

    number = int(callback.data.split(":")[1])
    site = get_user_site_by_number(callback.message.chat.id, number)

    if not site:
        await safe_edit(
            callback.message,
            "⚠️ Сайт не найден. Обнови список.",
            reply_markup=main_menu(),
        )
        return

    text = await build_site_card(site, number=number)

    await safe_edit(
        callback.message,
        text,
        reply_markup=site_card_menu(number),
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


@dp.callback_query(F.data == "menu_retro")
async def menu_retro(callback: types.CallbackQuery):
    await safe_answer(callback)

    text = (
        "🎧 Retro Mode\n\n"
        "📟 Пока сайты проверяются — включи немного "
        "олдскульного MIDI вайба.\n\n"
        "💾 Выбери трек ниже и включи ретро-настроение."
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

    if track not in TRACKS:
        await callback.message.answer("Трек не найден.")
        return

    path, title = TRACKS[track]

    await callback.message.answer_document(
        FSInputFile(BASE_DIR / path),
        caption=f"{title}\n\n🎧 Retro Monitoring Mode",
        reply_markup=after_track_menu()
    )



@dp.callback_query(F.data == "menu_cleanup")
async def menu_cleanup(callback: types.CallbackQuery):
    await safe_answer(callback)

    await safe_edit(
        callback.message,
        "⚠️ Сейчас будет очищена вся информация в этом чате.\n\n"
        "Нажмите OK, чтобы начать очистку. "
        "После очистки меню запустится автоматически.",
        reply_markup=cleanup_confirm_menu()
    )


@dp.callback_query(F.data == "cleanup_confirm")
async def cleanup_confirm(callback: types.CallbackQuery):
    await safe_answer(callback)

    chat_id = callback.message.chat.id
    current_message_id = callback.message.message_id

    await safe_edit(
        callback.message,
        "🧹 Очищаю чат..."
    )

    for msg_id in range(current_message_id, current_message_id - 100, -1):
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception:
            pass

    await bot.send_message(
        chat_id,
        "📡 Главное меню:",
        reply_markup=main_menu()
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


