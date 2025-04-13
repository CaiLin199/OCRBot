import os
import logging
from logging.handlers import RotatingFileHandler

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "0")
API_ID = int(os.environ.get("API_ID", "26254064"))
API_HASH = os.environ.get("API_HASH", "72541d6610ae7730e6135af9423b319c")
OWNER_ID = int(os.environ.get("OWNER_ID", "5296584067"))
MAIN_CHANNEL = int(os.environ.get("MAIN_CHANNEL", "-1002234026927"))
DB_CHANNEL = int(os.environ.get("DB_CHANNEL", "-1002279496397"))
OWNER_IDS = [int(x) for x in os.environ.get("OWNER_IDS", "5296584067,5364178811").split(',')]
PORT = os.environ.get("PORT", "8080")
TG_BOT_WORKERS = int(os.environ.get("TG_BOT_WORKERS", "1"))
LOG_FILE_NAME = "filesharingbot.txt"
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt='%d-%b-%y %H:%M:%S',
    handlers=[
        RotatingFileHandler(
            LOG_FILE_NAME,
            maxBytes=50000000,
            backupCount=10
        ),
        logging.StreamHandler()
    ]
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
