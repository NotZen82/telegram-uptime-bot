import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

# интервал проверки (сек)
CHECK_INTERVAL = 60

# How many failed checks in a row are needed before a DOWN alert.
FAILURE_THRESHOLD = int(os.getenv("FAILURE_THRESHOLD", "3"))
