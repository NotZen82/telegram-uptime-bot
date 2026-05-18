import requests
from aiogram import Bot
from db import get_sites, update_site_status


def normalize_url(url):
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"https://{url}"


def check_url(url):
    try:
        response = requests.get(normalize_url(url), timeout=10)
        return response.status_code < 400
    except requests.RequestException:
        return False


async def check_sites(bot: Bot):
    sites = get_sites()

    for site_id, url, chat_id, old_status in sites:
        is_up = check_url(url)
        new_status = "UP" if is_up else "DOWN"

        if old_status == "UNKNOWN":
            update_site_status(site_id, new_status)
            continue

        if old_status != new_status:
            update_site_status(site_id, new_status)

            if new_status == "DOWN":
                await bot.send_message(chat_id, f"🔴 Сайт упал: {url}")
            else:
                await bot.send_message(chat_id, f"🟢 Сайт снова работает: {url}")