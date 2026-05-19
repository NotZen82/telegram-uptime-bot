import requests
import socket
import ssl

from aiogram import Bot
from db import (
    get_sites,
    update_site_status,
    update_ssl_alert_status,
    add_incident
)

from datetime import datetime, timezone


def normalize_url(url):
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"https://{url}"


def check_url(url):
    try:
        full_url = url

        if not full_url.startswith("http"):
            full_url = f"https://{full_url}"

        response = requests.get(full_url, timeout=5)

        if response.status_code < 400:
            return "UP"

        return f"HTTP {response.status_code}"


    except requests.exceptions.Timeout:

        icon = "🔴"

        result = "timeout"


    except requests.exceptions.SSLError:

        icon = "🔴"

        result = "ssl error"


    except requests.exceptions.ConnectionError:

        icon = "🔴"

        result = "dns/connection error"


    except Exception:

        icon = "🔴"

        result = "unknown error"


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

        return (expires_date - datetime.now(timezone.utc)).days

    except Exception:
        return None


async def check_sites(bot: Bot):
    sites = get_sites()

    for site_id, url, chat_id, old_status, ssl_alert_sent in sites:
        new_status = check_url(url)

        if old_status == "UNKNOWN":
            update_site_status(site_id, new_status)

        elif old_status != new_status:
            update_site_status(site_id, new_status)
            add_incident(site_id, url, chat_id, new_status)

            if new_status != "UP":
                await bot.send_message(
                    chat_id,
                    f"🔴 Проблема с сайтом:\n\n"
                    f"🌐 {url}\n"
                    f"⚠️ {new_status}"
                )
            else:
                await bot.send_message(chat_id, f"🟢 Сайт снова работает: {url}")

        ssl_days = check_ssl_expiry(url)

        if ssl_days is None:
            continue

        if ssl_days <= 7 and not ssl_alert_sent:
            await bot.send_message(
                chat_id,
                f"⚠️ SSL сертификат скоро истекает:\n\n"
                f"🌐 {url}\n"
                f"🔐 Осталось дней: {ssl_days}"
            )
            update_ssl_alert_status(site_id, True)

        if ssl_days > 7 and ssl_alert_sent:
            update_ssl_alert_status(site_id, False)