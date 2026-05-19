import asyncio
import time
import socket
import ssl
import aiohttp

from datetime import datetime, timezone

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
    get_user_incidents
)

from checker import check_sites

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def safe_answer(callback):
    try:
        await safe_answer(callback)
    except:
        pass

# --------- COMMANDS ---------

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer(
        "👋 Uptime бот активен\n\n"
        "Выбери действие:",
        reply_markup=main_menu()
    )


def main_menu():
    builder = InlineKeyboardBuilder()

    builder.button(text="📋 Список сайтов", callback_data="menu_list")
    builder.button(text="📊 Статус", callback_data="menu_status")
    builder.button(text="🔎 Проверить сейчас", callback_data="menu_check")
    builder.button(text="📉 Инциденты", callback_data="menu_incidents")
    builder.button(text="➕ Как добавить сайт", callback_data="menu_add_help")
    builder.button(text="❓ FAQ", callback_data="menu_faq")

    builder.adjust(1)
    return builder.as_markup()


def refresh_menu():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="🔄 Обновить",
        callback_data="menu_check"
    )

    builder.button(
        text="⬅️ Меню",
        callback_data="menu_back"
    )

    builder.adjust(2)

    return builder.as_markup()


@dp.callback_query(F.data == "menu_incidents")
async def menu_incidents(callback: types.CallbackQuery):
    await safe_answer(callback)

    rows = get_user_incidents(callback.message.chat.id)

    if not rows:
        await callback.message.edit_text(
            "📭 Инцидентов пока нет.",
            reply_markup=main_menu()
        )
        return

    text = "📉 Последние инциденты:\n\n"

    for url, status, created_at in rows:
        icon = "🔴" if status == "DOWN" else "🟢"
        text += f"{icon} {url} — {status}\n"
        text += f"🕒 {created_at}\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=main_menu()
    )


@dp.message(Command("incidents"))
async def incidents(msg: types.Message):
    rows = get_user_incidents(msg.chat.id)

    if not rows:
        await msg.answer("📭 Инцидентов пока нет.")
        return

    text = "📉 Последние инциденты:\n\n"

    for url, status, created_at in rows:
        icon = "🔴" if status == "DOWN" else "🟢"
        text += f"{icon} {url} — {status}\n"
        text += f"🕒 {created_at}\n\n"

    await msg.answer(text)


def check_ssl_expiry(domain):
    try:
        domain = domain.replace("https://", "").replace("http://", "")
        domain = domain.split("/")[0]

        context = ssl.create_default_context()

        with socket.create_connection((domain, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()

        expires_str = cert["notAfter"]
        expires_date = datetime.strptime(
            expires_str,
            "%b %d %H:%M:%S %Y %Z"
        ).replace(tzinfo=timezone.utc)

        days_left = (expires_date - datetime.now(timezone.utc)).days

        return days_left

    except Exception:
        return None



def sites_menu(sites):
    builder = InlineKeyboardBuilder()

    for i, site in enumerate(sites, start=1):
        url, status = site
        builder.button(
            text=f"🗑 Удалить {i}",
            callback_data=f"delete_site:{i}"
        )

    builder.button(text="⬅️ Назад", callback_data="menu_back")
    builder.adjust(2)

    return builder.as_markup()


@dp.callback_query(F.data == "menu_back")
async def menu_back(callback: types.CallbackQuery):
    await safe_answer(callback)

    await callback.message.edit_text(
        "📡 Главное меню:",
        reply_markup=main_menu()
    )


@dp.callback_query(F.data == "menu_add_help")
async def menu_add_help(callback: types.CallbackQuery):
    await safe_answer(callback)

    await callback.message.edit_text(
        "➕ Чтобы добавить сайт, напиши:\n\n"
        "/add google.com",
        reply_markup=main_menu()
    )


@dp.callback_query(F.data == "menu_faq")
async def menu_faq(callback: types.CallbackQuery):
    await safe_answer(callback)

    text = (
        "❓ FAQ\n\n"

        "➕ Добавить сайт:\n"
        "/add google.com\n\n"

        "📋 Список сайтов:\n"
        "/list\n\n"

        "🗑 Удалить сайт:\n"
        "/remove 1\n\n"

        "🟢 UP — сайт работает\n"
        "🔴 DOWN — сайт недоступен\n\n"

        "🔐 SSL monitoring включён.\n"
        "Бот предупредит перед истечением сертификата."
    )

    await callback.message.edit_text(
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
            reply_markup=main_menu()
        )
        return

    text = "📋 Твои сайты:\n\n"

    for i, site in enumerate(sites, start=1):
        url, status = site

        if status == "UP":
            icon = "🟢"
        elif status == "DOWN":
            icon = "🔴"
        else:
            icon = "⚪"

        text += f"{i}. {icon} {url} — {status}\n"

    await callback.message.edit_text(
        text,
        reply_markup=sites_menu(sites)
    )


@dp.callback_query(F.data == "menu_status")
async def menu_status(callback: types.CallbackQuery):
    await safe_answer(callback)

    sites = get_user_sites(callback.message.chat.id)

    if not sites:
        await callback.message.edit_text(
            "📭 У тебя пока нет сайтов.",
            reply_markup=main_menu()
        )
        return

    up = down = unknown = 0

    for url, status in sites:
        if status == "UP":
            up += 1
        elif status == "DOWN":
            down += 1
        else:
            unknown += 1

    await callback.message.edit_text(
        "📊 Статус мониторинга:\n\n"
        f"🟢 UP: {up}\n"
        f"🔴 DOWN: {down}\n"
        f"⚪ UNKNOWN: {unknown}\n"
        f"Всего: {len(sites)}",
        reply_markup=main_menu()
    )


@dp.callback_query(F.data.startswith("delete_site:"))
async def delete_site_callback(callback: types.CallbackQuery):
    await safe_answer(callback)

    number = int(callback.data.split(":")[1])

    url = delete_site_by_number(
        callback.message.chat.id,
        number
    )

    if not url:
        await callback.message.edit_text(
            "⚠️ Сайт не найден. Обнови список.",
            reply_markup=main_menu()
        )
        return

    await callback.message.edit_text(
        f"🗑 Удалено: {url}",
        reply_markup=main_menu()
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


@dp.callback_query(F.data == "list")
async def callback_list(callback: types.CallbackQuery):
    sites = get_user_sites(callback.message.chat.id)

    if not sites:
        await callback.message.answer(
            "📭 У тебя пока нет сайтов."
        )
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

        text += f"{i}. {icon} {url}\n"

    await callback.message.answer(text)


@dp.callback_query(F.data == "status")
async def callback_status(callback: types.CallbackQuery):
    sites = get_user_sites(callback.message.chat.id)

    up = down = unknown = 0

    for url, status in sites:
        if status == "UP":
            up += 1
        elif status == "DOWN":
            down += 1
        else:
            unknown += 1

    await callback.message.answer(
        f"📊 Статус:\n\n"
        f"🟢 UP: {up}\n"
        f"🔴 DOWN: {down}\n"
        f"⚪ UNKNOWN: {unknown}"
    )


@dp.callback_query(F.data == "add")
async def callback_add(callback: types.CallbackQuery):
    await callback.message.answer(
        "Используй:\n/add google.com"
    )

async def check_site_async(session, url):
    full_url = url

    if not full_url.startswith("http"):
        full_url = f"https://{full_url}"

    try:
        start = time.time()

        async with session.get(
            full_url,
            timeout=aiohttp.ClientTimeout(total=5),
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"}
        ) as response:
            elapsed = round((time.time() - start) * 1000)
            status_code = response.status

            if status_code < 400:
                icon = "🟢"
            elif status_code < 500:
                icon = "🟠"
            else:
                icon = "🔴"

            result = f"HTTP {status_code} — {elapsed}ms"

            return url, icon, result

    except asyncio.TimeoutError:
        return url, "🔴", "timeout"

    except aiohttp.ClientConnectorCertificateError:
        return url, "🔴", "ssl error"

    except aiohttp.ClientConnectorError:
        return url, "🔴", "dns/connection error"

    except Exception:
        return url, "🔴", "unknown error"


@dp.callback_query(F.data == "menu_check")
async def callback_check(callback: types.CallbackQuery):
    await safe_answer(callback)

    sites = get_user_sites(callback.message.chat.id)

    if not sites:
        await callback.message.edit_text(
            "📭 У тебя нет сайтов для проверки.",
            reply_markup=main_menu()
        )
        return

    await callback.message.edit_text("🔄 Проверяю сайты...")

    text = "🔎 Проверка сайтов:\n\n"

    async with aiohttp.ClientSession() as session:
        tasks = [
            check_site_async(session, url)
            for url, status in sites
        ]

        results = await asyncio.gather(*tasks)

    for url, icon, result in results:
        ssl_days = check_ssl_expiry(url) if icon in ("🟢", "🟠") else None

        if ssl_days is None:
            ssl_text = ""
        elif ssl_days < 0:
            ssl_text = f"🔐 SSL expired {abs(ssl_days)} days ago"
        elif ssl_days <= 7:
            ssl_text = f"🔐 SSL expires in {ssl_days} days ⚠️"
        elif ssl_days <= 30:
            ssl_text = f"🔐 SSL expires in {ssl_days} days"
        else:
            ssl_text = f"🔐 SSL: {ssl_days} days"

        text += f"{icon} {url} — {result}\n"

        if ssl_text:
            text += f"{ssl_text}\n"

        text += "\n"

    await callback.message.edit_text(
        text,
        reply_markup=refresh_menu()
    )





@dp.message(Command("check"))
async def manual_check(msg: types.Message):
    sites = get_user_sites(msg.chat.id)

    if not sites:
        await msg.answer("📭 У тебя нет сайтов для проверки.")
        return

    text = "🔎 Проверка сайтов:\n\n"

    for url, status in sites:
        try:
            import requests

            full_url = url

            if not full_url.startswith("http"):
                full_url = f"https://{full_url}"

            response = requests.get(
                full_url,
                timeout=10,
                allow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            if response.status_code < 400:
                icon = "🟢"
                result = "UP"
            else:
                icon = "🔴"
                result = f"HTTP {response.status_code}"

        except:
            icon = "🔴"
            result = "DOWN"

        text += f"{icon} {url} — {result}\n"

    await msg.answer(text)


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


