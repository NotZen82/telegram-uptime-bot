import requests
from db import get_sites
from aiogram import Bot

async def check_sites(bot: Bot):
    sites = get_sites()

    for url, chat_id in sites:
        ok = False

        try:
            r = requests.get(f"http://{url}", timeout=5)
            ok = r.status_code < 400
        except:
            ok = False

        if not ok:
            await bot.send_message(
                chat_id,
                f"🔴 САЙТ УПАЛ: {url}"
            )
        else:
            print(f"{url} OK")