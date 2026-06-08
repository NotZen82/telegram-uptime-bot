import asyncio
from datetime import date, datetime
from pathlib import Path

from aiogram.types import FSInputFile

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.exceptions import TelegramUnauthorizedError

from config import BOT_TOKEN, CHECK_INTERVAL, FAILURE_THRESHOLD, FEEDBACK_CHAT_ID

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
    update_site_failure_threshold,
    update_site_ssl_monitoring,
    update_site_check_interval,
    update_site_display_name,
    update_site_domain_monitoring,
    update_site_domain_expires_at,
    get_chat_language,
    set_chat_language,
)

from checker import check_sites
from monitor import check_many_sites, ssl_text, domain_text, short_url


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
BASE_DIR = Path(__file__).resolve().parent
WAITING_FEEDBACK_USERS = set()
WAITING_SITE_SETTINGS = {}


TEXTS = {
    "ru": {
        "main_menu": "📡 Главное меню:",
        "menu_list": "📋 Список сайтов",
        "menu_status": "📊 Статус",
        "menu_check": "🔎 Проверить сейчас",
        "menu_incidents": "📉 Инциденты",
        "menu_add_help": "➕ Как добавить сайт",
        "menu_faq": "❓ FAQ",
        "menu_feedback": "💬 Обратная связь",
        "menu_retro": "🎧 Retro mode",
        "menu_cleanup": "🧹 Очистить чат",
        "menu_language": "🌐 Язык",
        "refresh": "🔄 Обновить",
        "back_menu": "⬅️ Меню",
        "back": "⬅️ Назад",
        "details": "ℹ️ Подробнее",
        "delete": "🗑 Удалить",
        "site_card": "⬅️ Карточка",
        "sites": "📋 Список",
        "settings": "⚙️ Настройки",
        "check": "🔄 Проверить",
        "language_title": "🌐 Выбери язык интерфейса:",
        "language_saved": "✅ Язык обновлен.",
        "no_sites_monitoring": "📭 У тебя пока нет сайтов для мониторинга.",
        "no_sites_check": "📭 У тебя нет сайтов для проверки.",
        "your_sites": "📋 Твои сайты:\n\n",
        "choose_site": "🌐 Выбери сайт:\n\n",
        "site_not_found": "⚠️ Сайт не найден. Проверь /list",
        "site_not_found_refresh": "⚠️ Сайт не найден. Обнови список.",
        "status_title": "📊 Статус мониторинга:",
        "total": "Всего",
        "checking_sites": "🔄 Проверяю сайты...",
        "check_title": "🔎 Проверка сайтов:\n\n",
        "no_incidents": "📭 Инцидентов пока нет.",
        "incidents_title": "📉 Последние инциденты:\n\n",
        "resolved": "восстановлен",
        "add_duplicate": "⚠️ Этот сайт уже есть в мониторинге: {url}",
        "added": "➕ Добавлено: {url}",
        "add_usage": "Используй: /add google.com",
        "remove_missing": "⚠️ Нет сайта с таким номером. Проверь /list",
        "removed": "🗑 Удалено: {url}",
        "remove_usage": "Используй: /remove 1 или /remove google.com",
        "domain_usage": "Используй: /domain 1 2026-05-10 или /domain 1 -",
        "domain_updated": "📅 Ручная дата домена обновлена: {value}",
        "domain_reset": "📅 Ручная дата домена сброшена.",
        "domain_invalid_date": "⚠️ Не понял дату. Используй формат YYYY-MM-DD, например 2026-05-10.",
        "myid": "Твой chat_id: {chat_id}",
        "feedback_not_configured": "⚠️ Обратная связь пока не настроена.",
        "feedback_title": "💬 Обратная связь",
        "feedback_prompt": (
            "Напиши, что сломалось, чего не хватает или что хочется улучшить.\n\n"
            "Следующее сообщение я отправлю разработчику."
        ),
        "cancel": "Отмена",
        "feedback_cancelled": "Ок, обратную связь отменил.",
        "feedback_failed": "⚠️ Не получилось отправить сообщение. Попробуй позже.",
        "feedback_sent": "Спасибо! Сообщение отправлено разработчику.",
        "feedback_new": "💬 Новая обратная связь",
        "none": "нет",
        "unknown": "неизвестно",
        "private_chat": "Личный чат с ботом",
        "no_text_forwarded": "Без текста. Сообщение переслано ниже.",
        "truncated": "...сообщение обрезано",
        "source": "Источник",
        "source_username": "Источник username",
        "chat_type": "Тип чата",
        "source_chat_id": "Chat ID источника",
        "message": "Сообщение",
        "add_help": "➕ Чтобы добавить сайт, напиши:\n\n/add google.com",
        "faq": (
            "❓ FAQ\n\n"
            "➕ Добавить сайт\n/add google.com\n\n"
            "📋 Список сайтов\n/list\n\n"
            "🌐 Карточка сайта\n/site 1\n\n"
            "📅 Ручной срок домена\n/domain 1 2026-05-10\n\n"
            "💬 Обратная связь\n/feedback\n\n"
            "🗑 Удалить сайт\n/remove 1\n\n"
            "🟢 UP — работает\n"
            "🟠 HTTP 4xx — предупреждение\n"
            "🔴 DOWN — недоступен\n\n"
            "🔐 SSL monitoring включен.\n"
            "Бот предупредит перед истечением сертификата.\n\n"
            "📅 Domain monitoring включен.\n"
            "Бот предупредит перед истечением регистрации домена.\n\n"
            "🌐 Сменить язык\n/lang"
        ),
        "site_settings_title": "⚙️ Настройки сайта {number}",
        "threshold": "🚦 Порог ошибок",
        "ssl_alerts": "🔐 SSL-алерты",
        "domain_alerts": "📅 Domain-алерты",
        "check_interval": "⏱ Интервал проверки",
        "site_name": "✏️ Имя",
        "enabled": "включен",
        "disabled": "выключен",
        "disable_ssl": "🔕 Выключить SSL",
        "enable_ssl": "🔔 Включить SSL",
        "disable_domain": "🔕 Выключить Domain",
        "enable_domain": "🔔 Включить Domain",
        "interval": "⏱ Интервал",
        "site_name_button": "✏️ Имя сайта",
        "db_status": "Статус в базе",
        "check_now": "Проверка сейчас",
        "errors_in_row": "Ошибок подряд",
        "last_incident": "Последний инцидент",
        "no_data": "нет данных",
        "setting_cancelled": "Ок, настройку отменил.",
        "threshold_prompt": "🚦 Введи новый порог ошибок от 1 до 10.\n\nНапример: 3",
        "interval_prompt": "⏱ Введи новый интервал проверки в минутах от 1 до 1440.\n\nНапример: 5",
        "name_prompt": "✏️ Введи новое имя сайта до 40 символов.\n\nЧтобы сбросить имя, отправь: -",
        "threshold_updated": "🚦 Порог ошибок обновлен: {value}",
        "interval_updated": "⏱ Интервал проверки обновлен: {value} min",
        "name_updated": "✏️ Имя сайта обновлено.",
        "invalid_setting": "⚠️ Не понял значение. Попробуй еще раз через настройки сайта.",
        "cleanup_confirm": (
            "⚠️ Сейчас будет очищена вся информация в этом чате.\n\n"
            "Нажмите OK, чтобы начать очистку. После очистки меню запустится автоматически."
        ),
        "cleaning": "🧹 Очищаю чат...",
        "track_not_found": "Трек не найден.",
        "retro_intro": (
            "🎧 Retro Mode\n\n"
            "📟 Пока сайты проверяются — включи немного олдскульного MIDI вайба.\n\n"
            "💾 Выбери трек ниже и включи ретро-настроение."
        ),
        "retro_command": (
            "🎧 Retro Monitoring Mode\n\n"
            "🎮 Doom vibes\n"
            "💾 Windows 95 mood\n"
            "🕹 8-bit terminal\n"
            "📟 Sysadmin after midnight"
        ),
    },
    "en": {
        "main_menu": "📡 Main menu:",
        "menu_list": "📋 Sites",
        "menu_status": "📊 Status",
        "menu_check": "🔎 Check now",
        "menu_incidents": "📉 Incidents",
        "menu_add_help": "➕ Add a site",
        "menu_faq": "❓ FAQ",
        "menu_feedback": "💬 Feedback",
        "menu_retro": "🎧 Retro mode",
        "menu_cleanup": "🧹 Clean chat",
        "menu_language": "🌐 Language",
        "refresh": "🔄 Refresh",
        "back_menu": "⬅️ Menu",
        "back": "⬅️ Back",
        "details": "ℹ️ Details",
        "delete": "🗑 Delete",
        "site_card": "⬅️ Site card",
        "sites": "📋 Sites",
        "settings": "⚙️ Settings",
        "check": "🔄 Check",
        "language_title": "🌐 Choose interface language:",
        "language_saved": "✅ Language updated.",
        "no_sites_monitoring": "📭 You do not have any monitored sites yet.",
        "no_sites_check": "📭 You do not have any sites to check.",
        "your_sites": "📋 Your sites:\n\n",
        "choose_site": "🌐 Choose a site:\n\n",
        "site_not_found": "⚠️ Site not found. Check /list",
        "site_not_found_refresh": "⚠️ Site not found. Refresh the list.",
        "status_title": "📊 Monitoring status:",
        "total": "Total",
        "checking_sites": "🔄 Checking sites...",
        "check_title": "🔎 Site check:\n\n",
        "no_incidents": "📭 No incidents yet.",
        "incidents_title": "📉 Recent incidents:\n\n",
        "resolved": "resolved",
        "add_duplicate": "⚠️ This site is already monitored: {url}",
        "added": "➕ Added: {url}",
        "add_usage": "Use: /add google.com",
        "remove_missing": "⚠️ There is no site with this number. Check /list",
        "removed": "🗑 Removed: {url}",
        "remove_usage": "Use: /remove 1 or /remove google.com",
        "domain_usage": "Use: /domain 1 2026-05-10 or /domain 1 -",
        "domain_updated": "📅 Manual domain date updated: {value}",
        "domain_reset": "📅 Manual domain date reset.",
        "domain_invalid_date": "⚠️ Could not understand the date. Use YYYY-MM-DD, for example 2026-05-10.",
        "myid": "Your chat_id: {chat_id}",
        "feedback_not_configured": "⚠️ Feedback is not configured yet.",
        "feedback_title": "💬 Feedback",
        "feedback_prompt": (
            "Write what broke, what is missing, or what you would like to improve.\n\n"
            "Your next message will be sent to the developer."
        ),
        "cancel": "Cancel",
        "feedback_cancelled": "Ok, feedback cancelled.",
        "feedback_failed": "⚠️ Could not send the message. Try again later.",
        "feedback_sent": "Thanks! Your message was sent to the developer.",
        "feedback_new": "💬 New feedback",
        "none": "none",
        "unknown": "unknown",
        "private_chat": "Private bot chat",
        "no_text_forwarded": "No text. The message is forwarded below.",
        "truncated": "...message truncated",
        "source": "Source",
        "source_username": "Source username",
        "chat_type": "Chat type",
        "source_chat_id": "Source chat ID",
        "message": "Message",
        "add_help": "➕ To add a site, send:\n\n/add google.com",
        "faq": (
            "❓ FAQ\n\n"
            "➕ Add a site\n/add google.com\n\n"
            "📋 Site list\n/list\n\n"
            "🌐 Site card\n/site 1\n\n"
            "📅 Manual domain expiry\n/domain 1 2026-05-10\n\n"
            "💬 Feedback\n/feedback\n\n"
            "🗑 Remove a site\n/remove 1\n\n"
            "🟢 UP — working\n"
            "🟠 HTTP 4xx — warning\n"
            "🔴 DOWN — unavailable\n\n"
            "🔐 SSL monitoring is enabled.\n"
            "The bot warns before certificate expiration.\n\n"
            "📅 Domain monitoring is enabled.\n"
            "The bot warns before domain registration expiration.\n\n"
            "🌐 Change language\n/lang"
        ),
        "site_settings_title": "⚙️ Site settings {number}",
        "threshold": "🚦 Failure threshold",
        "ssl_alerts": "🔐 SSL alerts",
        "domain_alerts": "📅 Domain alerts",
        "check_interval": "⏱ Check interval",
        "site_name": "✏️ Name",
        "enabled": "enabled",
        "disabled": "disabled",
        "disable_ssl": "🔕 Disable SSL",
        "enable_ssl": "🔔 Enable SSL",
        "disable_domain": "🔕 Disable Domain",
        "enable_domain": "🔔 Enable Domain",
        "interval": "⏱ Interval",
        "site_name_button": "✏️ Site name",
        "db_status": "Database status",
        "check_now": "Check now",
        "errors_in_row": "Failures in a row",
        "last_incident": "Last incident",
        "no_data": "no data",
        "setting_cancelled": "Ok, setting cancelled.",
        "threshold_prompt": "🚦 Enter a new failure threshold from 1 to 10.\n\nExample: 3",
        "interval_prompt": "⏱ Enter a new check interval in minutes from 1 to 1440.\n\nExample: 5",
        "name_prompt": "✏️ Enter a new site name, up to 40 characters.\n\nTo reset the name, send: -",
        "threshold_updated": "🚦 Failure threshold updated: {value}",
        "interval_updated": "⏱ Check interval updated: {value} min",
        "name_updated": "✏️ Site name updated.",
        "invalid_setting": "⚠️ Could not understand the value. Try again from site settings.",
        "cleanup_confirm": (
            "⚠️ This will clean recent bot messages in this chat.\n\n"
            "Press OK to start. The menu will be sent again automatically."
        ),
        "cleaning": "🧹 Cleaning chat...",
        "track_not_found": "Track not found.",
        "retro_intro": (
            "🎧 Retro Mode\n\n"
            "📟 While your sites are being checked, add some old-school MIDI mood.\n\n"
            "💾 Pick a track below."
        ),
        "retro_command": (
            "🎧 Retro Monitoring Mode\n\n"
            "🎮 Doom vibes\n"
            "💾 Windows 95 mood\n"
            "🕹 8-bit terminal\n"
            "📟 Sysadmin after midnight"
        ),
    },
}


def text(lang, key, **kwargs):
    value = TEXTS.get(lang, TEXTS["ru"]).get(key, TEXTS["ru"][key])
    return value.format(**kwargs) if kwargs else value


def get_lang(chat_id):
    return get_chat_language(chat_id) or "ru"


def detect_lang(message):
    language_code = getattr(message.from_user, "language_code", None) or ""
    return "ru" if language_code.lower().startswith("ru") else "en"


def ensure_lang(message):
    language = get_chat_language(message.chat.id)
    if language:
        return language

    language = detect_lang(message)
    set_chat_language(message.chat.id, language)
    return language


def masked_bot_token():
    if not BOT_TOKEN:
        return "empty"

    bot_id = BOT_TOKEN.split(":", 1)[0]
    return f"{bot_id}:***{BOT_TOKEN[-4:]}"


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


def main_menu(lang="ru"):
    builder = InlineKeyboardBuilder()

    builder.button(text=text(lang, "menu_list"), callback_data="menu_list")
    builder.button(text=text(lang, "menu_status"), callback_data="menu_status")
    builder.button(text=text(lang, "menu_check"), callback_data="menu_check")
    builder.button(text=text(lang, "menu_incidents"), callback_data="menu_incidents")
    builder.button(text=text(lang, "menu_add_help"), callback_data="menu_add_help")
    builder.button(text=text(lang, "menu_faq"), callback_data="menu_faq")
    builder.button(text=text(lang, "menu_feedback"), callback_data="menu_feedback")
    builder.button(text=text(lang, "menu_language"), callback_data="menu_language")
    builder.button(text=text(lang, "menu_retro"), callback_data="menu_retro")
    builder.button(text=text(lang, "menu_cleanup"), callback_data="menu_cleanup")


    builder.adjust(1)
    return builder.as_markup()


def refresh_menu(lang="ru"):
    builder = InlineKeyboardBuilder()

    builder.button(text=text(lang, "refresh"), callback_data="menu_check")
    builder.button(text=text(lang, "back_menu"), callback_data="menu_back")

    builder.adjust(2)
    return builder.as_markup()


def sites_menu(sites, lang="ru"):
    builder = InlineKeyboardBuilder()

    for i, _ in enumerate(sites, start=1):
        builder.button(
            text=f"{text(lang, 'details')} {i}",
            callback_data=f"site_detail:{i}",
        )
        builder.button(
            text=f"{text(lang, 'delete')} {i}",
            callback_data=f"delete_site:{i}",
        )

    builder.button(text=text(lang, "back"), callback_data="menu_back")
    builder.adjust(2)

    return builder.as_markup()


def site_display_name(url, display_name=None):
    return display_name or short_url(url)


def days_until(expires_at):
    if not expires_at:
        return None

    if isinstance(expires_at, datetime):
        expires_at = expires_at.date()

    if isinstance(expires_at, date):
        return (expires_at - date.today()).days

    return None


def site_number_menu(number, lang="ru"):
    builder = InlineKeyboardBuilder()

    builder.button(text=text(lang, "site_card"), callback_data=f"site_detail:{number}")
    builder.button(text=text(lang, "sites"), callback_data="menu_list")
    builder.button(text=text(lang, "back_menu"), callback_data="menu_back")

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


def build_status_text(sites, lang="ru"):
    up = down = unknown = 0

    for site in sites:
        status = site[1]

        if status == "UP":
            up += 1
        elif status == "UNKNOWN":
            unknown += 1
        else:
            down += 1

    return (
        f"{text(lang, 'status_title')}\n\n"
        f"🟢 UP: {up}\n"
        f"🔴 DOWN/ERROR: {down}\n"
        f"⚪ UNKNOWN: {unknown}\n"
        f"{text(lang, 'total')}: {len(sites)}"
    )


def build_check_text(results, lang="ru", manual_domain_days=None):
    manual_domain_days = manual_domain_days or {}
    check_text = text(lang, "check_title")

    for result in results:
        check_text += f"{result.icon} {short_url(result.url)} — {result.result}\n"

        ssl_info = ssl_text(result.ssl_days, lang=lang)

        if ssl_info:
            check_text += f"{ssl_info}\n"

        domain_days = manual_domain_days.get(result.url, result.domain_days)
        domain_info = domain_text(domain_days, lang=lang)

        if domain_info:
            check_text += f"{domain_info}\n"

        check_text += "\n"

    return check_text


def site_card_menu(number, lang="ru"):
    builder = InlineKeyboardBuilder()

    builder.button(text=text(lang, "check"), callback_data=f"site_detail:{number}")
    builder.button(text=text(lang, "settings"), callback_data=f"site_settings:{number}")
    builder.button(text=text(lang, "delete"), callback_data=f"delete_site:{number}")
    builder.button(text=text(lang, "sites"), callback_data="menu_list")
    builder.button(text=text(lang, "back_menu"), callback_data="menu_back")

    builder.adjust(2)
    return builder.as_markup()


def site_settings_menu(site, number, lang="ru"):
    builder = InlineKeyboardBuilder()

    ssl_enabled = site["ssl_monitoring_enabled"]
    ssl_text_button = text(lang, "disable_ssl") if ssl_enabled else text(lang, "enable_ssl")
    domain_enabled = site["domain_monitoring_enabled"]
    domain_text_button = text(lang, "disable_domain") if domain_enabled else text(lang, "enable_domain")

    builder.button(text=text(lang, "threshold"), callback_data=f"setting_threshold:{number}")
    builder.button(text=ssl_text_button, callback_data=f"setting_ssl:{number}")
    builder.button(text=domain_text_button, callback_data=f"setting_domain:{number}")
    builder.button(text=text(lang, "interval"), callback_data=f"setting_interval:{number}")
    builder.button(text=text(lang, "site_name_button"), callback_data=f"setting_name:{number}")
    builder.button(text=text(lang, "site_card"), callback_data=f"site_detail:{number}")
    builder.button(text=text(lang, "back_menu"), callback_data="menu_back")

    builder.adjust(2)
    return builder.as_markup()


def format_interval(seconds):
    if not seconds:
        return f"{CHECK_INTERVAL} sec (default)"

    if seconds % 60 == 0:
        return f"{seconds // 60} min"

    return f"{seconds} sec"


def build_site_settings_text(site, number, lang="ru"):
    threshold = site["failure_threshold"] or FAILURE_THRESHOLD
    ssl_status = text(lang, "enabled") if site["ssl_monitoring_enabled"] else text(lang, "disabled")
    domain_status = text(lang, "enabled") if site["domain_monitoring_enabled"] else text(lang, "disabled")
    name = site_display_name(site["url"], site["display_name"])

    return (
        f"{text(lang, 'site_settings_title', number=number)}\n\n"
        f"🌐 {name}\n"
        f"URL: {short_url(site['url'])}\n\n"
        f"{text(lang, 'threshold')}: {threshold}\n"
        f"{text(lang, 'ssl_alerts')}: {ssl_status}\n"
        f"{text(lang, 'domain_alerts')}: {domain_status}\n"
        f"{text(lang, 'check_interval')}: {format_interval(site['check_interval_seconds'])}\n"
        f"{text(lang, 'site_name')}: {name}"
    )


def format_incident_text(incident, lang="ru"):
    if not incident:
        return text(lang, "none")

    status = incident["status"]
    created_at = incident["created_at"]

    if status == "RESOLVED":
        duration = format_duration(incident["duration_seconds"])
        return f"{text(lang, 'resolved')}, {created_at}, downtime {duration}"

    return f"{status}, {created_at}"


async def build_site_card(site, number=None, lang="ru"):
    url = site["url"]
    status = site["status"]
    failure_count = site["failure_count"] or 0
    incident = get_last_site_incident(site["chat_id"], url)
    result = (await check_many_sites([url]))[0]

    ssl_info = ssl_text(result.ssl_days, lang=lang) or text(lang, "no_data")
    domain_days = days_until(site["domain_expires_at"])
    if domain_days is None:
        domain_days = result.domain_days

    domain_info = domain_text(domain_days, lang=lang) or text(lang, "no_data")
    status_icon = render_status_icon(status)

    title = f"🌐 {short_url(url)}"
    if number:
        title = f"{number}. {title}"

    return (
        f"{title}\n\n"
        f"{text(lang, 'db_status')}: {status_icon} {status}\n"
        f"{text(lang, 'check_now')}: {result.icon} {result.result}\n"
        f"SSL: {ssl_info}\n"
        f"Domain: {domain_info}\n"
        f"{text(lang, 'errors_in_row')}: {failure_count}/{site['failure_threshold'] or FAILURE_THRESHOLD}\n"
        f"{text(lang, 'last_incident')}: {format_incident_text(incident, lang)}"
    )


def retro_menu(lang="ru"):
    builder = InlineKeyboardBuilder()

    for key, (_, title) in TRACKS.items():
        builder.button(
            text=title,
            callback_data=f"retro:{key}"
        )

    builder.button(
        text=text(lang, "back_menu"),
        callback_data="menu_back"
    )

    builder.adjust(1)

    return builder.as_markup()

def after_track_menu(lang="ru"):
    builder = InlineKeyboardBuilder()

    builder.button(text=text(lang, "menu_cleanup"), callback_data="menu_cleanup")
    builder.button(text=text(lang, "back_menu"), callback_data="menu_back")

    builder.adjust(2)
    return builder.as_markup()


def cleanup_confirm_menu(lang="ru"):
    builder = InlineKeyboardBuilder()

    builder.button(text="OK", callback_data="cleanup_confirm")
    builder.button(text=text(lang, "back_menu"), callback_data="menu_back")

    builder.adjust(2)
    return builder.as_markup()


def feedback_menu(lang="ru"):
    builder = InlineKeyboardBuilder()

    builder.button(text=text(lang, "cancel"), callback_data="feedback_cancel")
    builder.button(text=text(lang, "back_menu"), callback_data="menu_back")

    builder.adjust(2)
    return builder.as_markup()


def feedback_prompt_text(lang="ru"):
    return (
        f"{text(lang, 'feedback_title')}\n\n"
        f"{text(lang, 'feedback_prompt')}"
    )


def language_menu():
    builder = InlineKeyboardBuilder()

    builder.button(text="Русский", callback_data="set_lang:ru")
    builder.button(text="English", callback_data="set_lang:en")

    builder.adjust(2)
    return builder.as_markup()


async def ask_feedback(message):
    lang = get_lang(message.chat.id)

    if not FEEDBACK_CHAT_ID:
        await message.answer(
            text(lang, "feedback_not_configured")
        )
        return

    WAITING_FEEDBACK_USERS.add(message.chat.id)

    await message.answer(
        feedback_prompt_text(lang),
        reply_markup=feedback_menu(lang)
    )


async def send_feedback_to_admin(msg: types.Message):
    lang = get_lang(msg.chat.id)
    user = msg.from_user
    username = f"@{user.username}" if user and user.username else text(lang, "none")
    full_name = user.full_name if user else text(lang, "unknown")
    source_title = msg.chat.title or text(lang, "private_chat")
    source_username = f"@{msg.chat.username}" if msg.chat.username else text(lang, "none")
    feedback_text = msg.text or msg.caption or text(lang, "no_text_forwarded")

    if len(feedback_text) > 3000:
        feedback_text = f"{feedback_text[:3000]}\n\n{text(lang, 'truncated')}"

    await bot.send_message(
        FEEDBACK_CHAT_ID,
        f"{text(lang, 'feedback_new')}\n\n"
        f"Name: {full_name}\n"
        f"Username: {username}\n"
        f"User ID: {msg.from_user.id if msg.from_user else msg.chat.id}\n"
        f"{text(lang, 'source')}: {source_title}\n"
        f"{text(lang, 'source_username')}: {source_username}\n"
        f"{text(lang, 'chat_type')}: {msg.chat.type}\n"
        f"{text(lang, 'source_chat_id')}: {msg.chat.id}\n\n"
        f"{text(lang, 'message')}:\n{feedback_text}"
    )

    if not msg.text:
        await bot.forward_message(
            FEEDBACK_CHAT_ID,
            msg.chat.id,
            msg.message_id
        )


# --------- COMMANDS ---------

@dp.message(Command("start"))
async def start(msg: types.Message):
    lang = ensure_lang(msg)
    chat_id = msg.chat.id
    current_message_id = msg.message_id

    for msg_id in range(current_message_id, current_message_id - 100, -1):
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception:
            pass

    await bot.send_message(
        chat_id,
        text(lang, "main_menu"),
        reply_markup=main_menu(lang)
    )


@dp.message(Command("lang"))
async def language(msg: types.Message):
    lang = ensure_lang(msg)
    await msg.answer(
        text(lang, "language_title"),
        reply_markup=language_menu()
    )


@dp.message(Command("add"))
async def add(msg: types.Message):
    lang = ensure_lang(msg)

    try:
        url = msg.text.split(" ", 1)[1].strip().lower()

        if not url:
            raise ValueError

        if site_exists(url, msg.chat.id):
            await msg.answer(text(lang, "add_duplicate", url=url))
            return

        add_site(url, msg.chat.id)
        await msg.answer(text(lang, "added", url=url))

    except Exception:
        await msg.answer(text(lang, "add_usage"))


@dp.message(Command("remove"))
async def remove(msg: types.Message):
    lang = ensure_lang(msg)

    try:
        value = msg.text.split(" ", 1)[1].strip()

        if value.isdigit():
            url = delete_site_by_number(msg.chat.id, int(value))

            if not url:
                await msg.answer(text(lang, "remove_missing"))
                return

            await msg.answer(text(lang, "removed", url=url))
            return

        delete_site(value.lower(), msg.chat.id)
        await msg.answer(text(lang, "removed", url=value.lower()))

    except Exception:
        await msg.answer(text(lang, "remove_usage"))


@dp.message(Command("domain"))
async def set_domain_expiry(msg: types.Message):
    lang = ensure_lang(msg)

    try:
        parts = msg.text.split(maxsplit=2)
        if len(parts) != 3:
            await msg.answer(text(lang, "domain_usage"))
            return

        _, number_text, value = parts
        number = int(number_text)
        site = get_user_site_by_number(msg.chat.id, number)

        if not site:
            await msg.answer(text(lang, "site_not_found_refresh"))
            return

        value = value.strip()

        if value in ("-", "reset", "none"):
            update_site_domain_expires_at(site["id"], None)
            await msg.answer(text(lang, "domain_reset"))
            return

        expires_at = datetime.strptime(value, "%Y-%m-%d").date()
        update_site_domain_expires_at(site["id"], expires_at)
        await msg.answer(text(lang, "domain_updated", value=expires_at.isoformat()))

    except ValueError:
        await msg.answer(text(lang, "domain_invalid_date"))

    except Exception:
        await msg.answer(text(lang, "domain_usage"))


@dp.message(Command("list"))
async def list_sites(msg: types.Message):
    lang = ensure_lang(msg)
    sites = get_user_sites(msg.chat.id)

    if not sites:
        await msg.answer(text(lang, "no_sites_monitoring"))
        return

    list_text = text(lang, "your_sites")

    for i, (url, status, display_name, _) in enumerate(sites, start=1):
        icon = render_status_icon(status)
        list_text += f"{i}. {icon} {site_display_name(url, display_name)} — {status}\n"

    await msg.answer(list_text)


@dp.message(Command("site"))
async def site_card(msg: types.Message):
    lang = ensure_lang(msg)
    sites = get_user_sites(msg.chat.id)

    if not sites:
        await msg.answer(text(lang, "no_sites_monitoring"))
        return

    try:
        value = msg.text.split(" ", 1)[1].strip().lower()
    except Exception:
        sites_text = text(lang, "choose_site")

        for i, (url, status, display_name, _) in enumerate(sites, start=1):
            icon = render_status_icon(status)
            sites_text += f"{i}. {icon} {site_display_name(url, display_name)} — {status}\n"

        await msg.answer(
            sites_text,
            reply_markup=sites_menu(sites, lang),
        )
        return

    if value.isdigit():
        number = int(value)
        site = get_user_site_by_number(msg.chat.id, number)
    else:
        number = None
        site = get_user_site_detail(msg.chat.id, value)

    if not site:
        await msg.answer(text(lang, "site_not_found"))
        return

    card_text = await build_site_card(site, number=number, lang=lang)

    await msg.answer(
        card_text,
        reply_markup=site_card_menu(number, lang) if number else main_menu(lang),
    )


@dp.message(Command("status"))
async def status_summary(msg: types.Message):
    lang = ensure_lang(msg)
    sites = get_user_sites(msg.chat.id)

    if not sites:
        await msg.answer(text(lang, "no_sites_monitoring"))
        return

    await msg.answer(build_status_text(sites, lang))


@dp.message(Command("check"))
async def manual_check(msg: types.Message):
    lang = ensure_lang(msg)
    sites = get_user_sites(msg.chat.id)

    if not sites:
        await msg.answer(text(lang, "no_sites_check"))
        return

    await msg.answer(text(lang, "checking_sites"))

    urls = [site[0] for site in sites]
    manual_domain_days = {
        url: days_until(domain_expires_at)
        for url, _, _, domain_expires_at in sites
        if domain_expires_at
    }
    results = await check_many_sites(urls)

    await msg.answer(build_check_text(results, lang, manual_domain_days))


@dp.message(Command("incidents"))
async def incidents(msg: types.Message):
    lang = ensure_lang(msg)
    rows = get_user_incidents(msg.chat.id)

    if not rows:
        await msg.answer(text(lang, "no_incidents"))
        return

    incidents_text = text(lang, "incidents_title")

    for url, status, created_at in rows:
        if status == "RESOLVED":
            icon = "🟢"
            status_text = text(lang, "resolved")
        elif status == "UP":
            icon = "🟢"
            status_text = "UP"
        else:
            icon = "🔴"
            status_text = status

        incidents_text += f"{icon} {short_url(url)} — {status_text}\n"
        incidents_text += f"🕒 {created_at}\n\n"

    await msg.answer(incidents_text)


@dp.message(Command("feedback"))
async def feedback(msg: types.Message):
    await ask_feedback(msg)


@dp.message(Command("myid"))
async def myid(msg: types.Message):
    lang = ensure_lang(msg)
    await msg.answer(text(lang, "myid", chat_id=msg.chat.id))


@dp.message(lambda msg: msg.chat.id in WAITING_SITE_SETTINGS)
async def receive_site_setting(msg: types.Message):
    lang = ensure_lang(msg)
    state = WAITING_SITE_SETTINGS.pop(msg.chat.id)
    number = state["number"]
    setting = state["setting"]
    site = get_user_site_by_number(msg.chat.id, number)

    if not site:
        await msg.answer(text(lang, "site_not_found_refresh"), reply_markup=main_menu(lang))
        return

    value = (msg.text or "").strip()

    if value.startswith("/"):
        await msg.answer(text(lang, "setting_cancelled"), reply_markup=site_number_menu(number, lang))
        return

    try:
        if setting == "threshold":
            threshold = int(value)

            if threshold < 1 or threshold > 10:
                raise ValueError

            update_site_failure_threshold(site["id"], threshold)
            message = text(lang, "threshold_updated", value=threshold)

        elif setting == "interval":
            minutes = int(value)

            if minutes < 1 or minutes > 1440:
                raise ValueError

            update_site_check_interval(site["id"], minutes * 60)
            message = text(lang, "interval_updated", value=minutes)

        elif setting == "name":
            if len(value) > 40:
                raise ValueError

            display_name = None if value in ("-", "—") else value
            update_site_display_name(site["id"], display_name)
            message = text(lang, "name_updated")

        else:
            raise ValueError

    except ValueError:
        await msg.answer(
            text(lang, "invalid_setting"),
            reply_markup=site_number_menu(number, lang)
        )
        return

    await msg.answer(message, reply_markup=site_number_menu(number, lang))


@dp.message(Command("retro"))
async def retro(msg: types.Message):
    lang = ensure_lang(msg)
    await msg.answer(
        text(lang, "retro_command")
    )


@dp.message(lambda msg: msg.chat.id in WAITING_FEEDBACK_USERS)
async def receive_feedback(msg: types.Message):
    lang = ensure_lang(msg)

    if msg.text and msg.text.startswith("/"):
        WAITING_FEEDBACK_USERS.discard(msg.chat.id)
        await msg.answer(
            text(lang, "feedback_cancelled"),
            reply_markup=main_menu(lang)
        )
        return

    try:
        await send_feedback_to_admin(msg)
    except Exception:
        await msg.answer(
            text(lang, "feedback_failed"),
            reply_markup=main_menu(lang)
        )
        return

    WAITING_FEEDBACK_USERS.discard(msg.chat.id)

    await msg.answer(
        text(lang, "feedback_sent"),
        reply_markup=main_menu(lang)
    )


# --------- CALLBACKS ---------

@dp.callback_query(F.data == "menu_back")
async def menu_back(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)
    WAITING_FEEDBACK_USERS.discard(callback.message.chat.id)
    WAITING_SITE_SETTINGS.pop(callback.message.chat.id, None)

    await safe_edit(
        callback.message,
        text(lang, "main_menu"),
        reply_markup=main_menu(lang),
    )


@dp.callback_query(F.data == "menu_language")
async def menu_language(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    await safe_edit(
        callback.message,
        text(lang, "language_title"),
        reply_markup=language_menu(),
    )


@dp.callback_query(F.data.startswith("set_lang:"))
async def set_language_callback(callback: types.CallbackQuery):
    language = callback.data.split(":")[1]
    if language not in TEXTS:
        language = "ru"

    set_chat_language(callback.message.chat.id, language)
    await safe_answer(callback)

    await safe_edit(
        callback.message,
        f"{text(language, 'language_saved')}\n\n{text(language, 'main_menu')}",
        reply_markup=main_menu(language),
    )


@dp.callback_query(F.data == "menu_add_help")
async def menu_add_help(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    await safe_edit(
        callback.message,
        text(lang, "add_help"),
        reply_markup=main_menu(lang),
    )


@dp.callback_query(F.data == "menu_faq")
async def menu_faq(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    await safe_edit(
        callback.message,
        text(lang, "faq"),
        reply_markup=main_menu(lang)
    )


@dp.callback_query(F.data == "menu_feedback")
async def menu_feedback(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    if not FEEDBACK_CHAT_ID:
        await safe_edit(
            callback.message,
            text(lang, "feedback_not_configured"),
            reply_markup=main_menu(lang)
        )
        return

    WAITING_FEEDBACK_USERS.add(callback.message.chat.id)

    await safe_edit(
        callback.message,
        feedback_prompt_text(lang),
        reply_markup=feedback_menu(lang)
    )


@dp.callback_query(F.data == "feedback_cancel")
async def feedback_cancel(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)
    WAITING_FEEDBACK_USERS.discard(callback.message.chat.id)

    await safe_edit(
        callback.message,
        text(lang, "main_menu"),
        reply_markup=main_menu(lang),
    )


@dp.callback_query(F.data == "menu_list")
async def menu_list(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    sites = get_user_sites(callback.message.chat.id)

    if not sites:
        await safe_edit(
            callback.message,
            f"{text(lang, 'no_sites_monitoring')}\n\n"
            f"{text(lang, 'add_usage')}",
            reply_markup=main_menu(lang),
        )
        return

    list_text = text(lang, "your_sites")

    for i, (url, status, display_name, _) in enumerate(sites, start=1):
        icon = render_status_icon(status)
        list_text += f"{i}. {icon} {site_display_name(url, display_name)} — {status}\n"

    await safe_edit(
        callback.message,
        list_text,
        reply_markup=sites_menu(sites, lang),
    )


@dp.callback_query(F.data == "menu_status")
async def menu_status(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    sites = get_user_sites(callback.message.chat.id)

    if not sites:
        await safe_edit(
            callback.message,
            text(lang, "no_sites_monitoring"),
            reply_markup=main_menu(lang),
        )
        return

    await safe_edit(
        callback.message,
        build_status_text(sites, lang),
        reply_markup=main_menu(lang),
    )


@dp.callback_query(F.data == "menu_incidents")
async def menu_incidents(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    rows = get_user_incidents(callback.message.chat.id)

    if not rows:
        await safe_edit(
            callback.message,
            text(lang, "no_incidents"),
            reply_markup=main_menu(lang)
        )
        return

    incidents_text = text(lang, "incidents_title")

    for url, status, created_at in rows:
        if status == "RESOLVED":
            icon = "🟢"
            status_text = text(lang, "resolved")
        elif status == "UP":
            icon = "🟢"
            status_text = "UP"
        else:
            icon = "🔴"
            status_text = status

        incidents_text += f"{icon} {short_url(url)} — {status_text}\n"
        incidents_text += f"🕒 {created_at}\n\n"

    await safe_edit(
        callback.message,
        incidents_text,
        reply_markup=main_menu(lang)
    )


@dp.callback_query(F.data.startswith("delete_site:"))
async def delete_site_callback(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    number = int(callback.data.split(":")[1])

    url = delete_site_by_number(
        callback.message.chat.id,
        number,
    )

    if not url:
        await safe_edit(
            callback.message,
            text(lang, "site_not_found_refresh"),
            reply_markup=main_menu(lang),
        )
        return

    await safe_edit(
        callback.message,
        text(lang, "removed", url=short_url(url)),
        reply_markup=main_menu(lang),
    )


@dp.callback_query(F.data.startswith("site_detail:"))
async def site_detail_callback(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    number = int(callback.data.split(":")[1])
    site = get_user_site_by_number(callback.message.chat.id, number)

    if not site:
        await safe_edit(
            callback.message,
            text(lang, "site_not_found_refresh"),
            reply_markup=main_menu(lang),
        )
        return

    card_text = await build_site_card(site, number=number, lang=lang)

    await safe_edit(
        callback.message,
        card_text,
        reply_markup=site_card_menu(number, lang),
    )


@dp.callback_query(F.data.startswith("site_settings:"))
async def site_settings_callback(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    number = int(callback.data.split(":")[1])
    site = get_user_site_by_number(callback.message.chat.id, number)

    if not site:
        await safe_edit(
            callback.message,
            text(lang, "site_not_found_refresh"),
            reply_markup=main_menu(lang),
        )
        return

    await safe_edit(
        callback.message,
        build_site_settings_text(site, number, lang),
        reply_markup=site_settings_menu(site, number, lang),
    )


@dp.callback_query(F.data.startswith("setting_ssl:"))
async def setting_ssl_callback(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    number = int(callback.data.split(":")[1])
    site = get_user_site_by_number(callback.message.chat.id, number)

    if not site:
        await safe_edit(callback.message, text(lang, "site_not_found_refresh"), reply_markup=main_menu(lang))
        return

    enabled = not site["ssl_monitoring_enabled"]
    update_site_ssl_monitoring(site["id"], enabled)
    site = get_user_site_by_number(callback.message.chat.id, number)

    await safe_edit(
        callback.message,
        build_site_settings_text(site, number, lang),
        reply_markup=site_settings_menu(site, number, lang),
    )


@dp.callback_query(F.data.startswith("setting_domain:"))
async def setting_domain_callback(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    number = int(callback.data.split(":")[1])
    site = get_user_site_by_number(callback.message.chat.id, number)

    if not site:
        await safe_edit(callback.message, text(lang, "site_not_found_refresh"), reply_markup=main_menu(lang))
        return

    enabled = not site["domain_monitoring_enabled"]
    update_site_domain_monitoring(site["id"], enabled)
    site = get_user_site_by_number(callback.message.chat.id, number)

    await safe_edit(
        callback.message,
        build_site_settings_text(site, number, lang),
        reply_markup=site_settings_menu(site, number, lang),
    )


@dp.callback_query(F.data.startswith("setting_threshold:"))
async def setting_threshold_callback(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    number = int(callback.data.split(":")[1])
    WAITING_SITE_SETTINGS[callback.message.chat.id] = {
        "number": number,
        "setting": "threshold",
    }

    await safe_edit(
        callback.message,
        text(lang, "threshold_prompt"),
        reply_markup=site_number_menu(number, lang),
    )


@dp.callback_query(F.data.startswith("setting_interval:"))
async def setting_interval_callback(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    number = int(callback.data.split(":")[1])
    WAITING_SITE_SETTINGS[callback.message.chat.id] = {
        "number": number,
        "setting": "interval",
    }

    await safe_edit(
        callback.message,
        text(lang, "interval_prompt"),
        reply_markup=site_number_menu(number, lang),
    )


@dp.callback_query(F.data.startswith("setting_name:"))
async def setting_name_callback(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    number = int(callback.data.split(":")[1])
    WAITING_SITE_SETTINGS[callback.message.chat.id] = {
        "number": number,
        "setting": "name",
    }

    await safe_edit(
        callback.message,
        text(lang, "name_prompt"),
        reply_markup=site_number_menu(number, lang),
    )


@dp.callback_query(F.data == "menu_check")
async def callback_check(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    sites = get_user_sites(callback.message.chat.id)

    if not sites:
        await safe_edit(
            callback.message,
            text(lang, "no_sites_check"),
            reply_markup=main_menu(lang),
        )
        return

    await safe_edit(callback.message, text(lang, "checking_sites"))

    urls = [site[0] for site in sites]
    manual_domain_days = {
        url: days_until(domain_expires_at)
        for url, _, _, domain_expires_at in sites
        if domain_expires_at
    }
    results = await check_many_sites(urls)

    await safe_edit(
        callback.message,
        build_check_text(results, lang, manual_domain_days),
        reply_markup=refresh_menu(lang),
    )


@dp.callback_query(F.data == "menu_retro")
async def menu_retro(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    await safe_edit(
        callback.message,
        text(lang, "retro_intro"),
        reply_markup=retro_menu(lang)
    )


@dp.callback_query(F.data.startswith("retro:"))
async def retro_track(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    track = callback.data.split(":")[1]

    if track not in TRACKS:
        await callback.message.answer(text(lang, "track_not_found"))
        return

    path, title = TRACKS[track]

    await callback.message.answer_document(
        FSInputFile(BASE_DIR / path),
        caption=f"{title}\n\n🎧 Retro Monitoring Mode",
        reply_markup=after_track_menu(lang)
    )



@dp.callback_query(F.data == "menu_cleanup")
async def menu_cleanup(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    await safe_edit(
        callback.message,
        text(lang, "cleanup_confirm"),
        reply_markup=cleanup_confirm_menu(lang)
    )


@dp.callback_query(F.data == "cleanup_confirm")
async def cleanup_confirm(callback: types.CallbackQuery):
    await safe_answer(callback)
    lang = get_lang(callback.message.chat.id)

    chat_id = callback.message.chat.id
    current_message_id = callback.message.message_id

    await safe_edit(
        callback.message,
        text(lang, "cleaning")
    )

    for msg_id in range(current_message_id, current_message_id - 100, -1):
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception:
            pass

    await bot.send_message(
        chat_id,
        text(lang, "main_menu"),
        reply_markup=main_menu(lang)
    )


# --------- BACKGROUND JOB ---------

async def scheduler_task():
    await check_sites(bot)


async def main():
    init_db()

    try:
        me = await bot.get_me()
        print(
            f"Telegram bot authorized: @{me.username} "
            f"(id={me.id}, token={masked_bot_token()})",
            flush=True,
        )
    except TelegramUnauthorizedError:
        print(
            "Telegram bot authorization failed. "
            f"Check Railway BOT_TOKEN. Runtime token={masked_bot_token()}",
            flush=True,
        )
        raise

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


