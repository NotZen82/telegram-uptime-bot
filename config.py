import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
FEEDBACK_CHAT_ID = os.getenv("FEEDBACK_CHAT_ID", "").strip()

if FEEDBACK_CHAT_ID and FEEDBACK_CHAT_ID.lstrip("-").isdigit():
    FEEDBACK_CHAT_ID = int(FEEDBACK_CHAT_ID)

# интервал проверки (сек)
CHECK_INTERVAL = 60

# How many failed checks in a row are needed before a DOWN alert.
FAILURE_THRESHOLD = int(os.getenv("FAILURE_THRESHOLD", "3"))
