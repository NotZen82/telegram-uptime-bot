import asyncio
import socket
import ssl
from datetime import datetime, timezone

import requests
from aiogram import Bot

from config import FAILURE_THRESHOLD
from db import (
    get_sites,
    update_site_status,
    update_failure_count,
    reset_failure_count,
    update_site_checked_at,
    update_ssl_alert_status,
    open_incident,
    close_incident,
    format_duration,
    get_chat_language,
)


async def auto_delete(message, delay=60):
    await asyncio.sleep(delay)

    try:
        await message.delete()
    except Exception:
        pass


def normalize_url(url):
    if url.startswith("http://") or url.startswith("https://"):
        return url

    return f"https://{url}"


def check_url(url):
    try:
        response = requests.get(
            normalize_url(url),
            timeout=5,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        if response.status_code < 400:
            return "UP"

        if response.status_code < 500:
            return f"HTTP {response.status_code}"

        return f"HTTP {response.status_code}"

    except requests.exceptions.Timeout:
        return "TIMEOUT"

    except requests.exceptions.SSLError:
        return "SSL ERROR"

    except requests.exceptions.ConnectionError:
        return "CONNECTION ERROR"

    except requests.exceptions.InvalidURL:
        return "INVALID URL"

    except requests.exceptions.TooManyRedirects:
        return "TOO MANY REDIRECTS"

    except requests.exceptions.RequestException:
        return "REQUEST ERROR"

    except Exception:
        return "UNKNOWN ERROR"


def check_ssl_expiry(domain):
    try:
        domain = domain.replace("https://", "").replace("http://", "")
        domain = domain.split("/")[0]

        context = ssl.create_default_context()

        with socket.create_connection((domain, 443), timeout=5) as sock:
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


async def send_auto_delete(bot, chat_id, text):
    message = await bot.send_message(chat_id, text)
    asyncio.create_task(auto_delete(message, delay=60))


def alert_text(lang, kind, url, **kwargs):
    if lang == "en":
        if kind == "up":
            return (
                f"🟢 Site is back online:\n\n"
                f"🌐 {url}\n"
                f"⏱ Downtime: {kwargs['duration']}"
            )

        if kind == "down":
            return (
                f"🔴 Site problem:\n\n"
                f"🌐 {url}\n"
                f"⚠️ {kwargs['status']}\n"
                f"Failed checks in a row: {kwargs['failure_count']}"
            )

        if kind == "ssl":
            return (
                f"⚠️ SSL certificate expires soon:\n\n"
                f"🌐 {url}\n"
                f"🔐 Days left: {kwargs['ssl_days']}"
            )

    if kind == "up":
        return (
            f"🟢 Сайт снова работает:\n\n"
            f"🌐 {url}\n"
            f"⏱ Downtime: {kwargs['duration']}"
        )

    if kind == "down":
        return (
            f"🔴 Проблема с сайтом:\n\n"
            f"🌐 {url}\n"
            f"⚠️ {kwargs['status']}\n"
            f"Проверок подряд с ошибкой: {kwargs['failure_count']}"
        )

    return (
        f"⚠️ SSL сертификат скоро истекает:\n\n"
        f"🌐 {url}\n"
        f"🔐 Осталось дней: {kwargs['ssl_days']}"
    )


async def check_sites(bot: Bot):
    sites = get_sites()

    for site in sites:
        site_id = site["id"]
        url = site["url"]
        chat_id = site["chat_id"]
        old_status = site["status"]
        lang = get_chat_language(chat_id) or "ru"
        ssl_alert_sent = site["ssl_alert_sent"]
        failure_count = site["failure_count"]
        failure_threshold = site["failure_threshold"] or FAILURE_THRESHOLD
        check_interval = site["check_interval_seconds"]
        last_checked_at = site["last_checked_at"]
        ssl_monitoring_enabled = site["ssl_monitoring_enabled"]

        if check_interval and last_checked_at:
            elapsed = (datetime.now() - last_checked_at).total_seconds()

            if elapsed < check_interval:
                continue

        new_status = check_url(url)
        update_site_checked_at(site_id)

        if new_status == "UP":
            reset_failure_count(site_id)

            if old_status == "UNKNOWN":
                update_site_status(site_id, new_status)

            elif old_status != "UP":
                update_site_status(site_id, new_status)

                duration_seconds = close_incident(site_id)
                duration = format_duration(duration_seconds)

                await send_auto_delete(
                    bot,
                    chat_id,
                    alert_text(lang, "up", url, duration=duration)
                )

        else:
            failure_count = (failure_count or 0) + 1
            update_failure_count(site_id, failure_count)

            if old_status not in ("UP", "UNKNOWN"):
                if old_status != new_status:
                    update_site_status(site_id, new_status)

            elif failure_count >= failure_threshold:
                update_site_status(site_id, new_status)
                open_incident(site_id, url, chat_id, new_status)

                await send_auto_delete(
                    bot,
                    chat_id,
                    alert_text(
                        lang,
                        "down",
                        url,
                        status=new_status,
                        failure_count=failure_count,
                    )
                )

        if not ssl_monitoring_enabled:
            if ssl_alert_sent:
                update_ssl_alert_status(site_id, False)
            continue

        ssl_days = check_ssl_expiry(url)

        if ssl_days is None:
            continue

        if ssl_days <= 7 and not ssl_alert_sent:
            await send_auto_delete(
                bot,
                chat_id,
                alert_text(lang, "ssl", url, ssl_days=ssl_days)
            )

            update_ssl_alert_status(site_id, True)

        if ssl_days > 7 and ssl_alert_sent:
            update_ssl_alert_status(site_id, False)
