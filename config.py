import os
import logging
from logging.handlers import RotatingFileHandler

# Bot Configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "0")
API_ID = int(os.environ.get("API_ID", "26254064"))
API_HASH = os.environ.get("API_HASH", "72541d6610ae7730e6135af9423b319c")
OWNER_ID = int(os.environ.get("OWNER_ID", "5296584067"))
MAIN_CHANNEL = int(os.environ.get("MAIN_CHANNEL", "-1002372552947"))
CHANNEL_ID = int(os.environ.get("DB_CHANNEL", "-1002279496397"))
OWNER_IDS = [int(x) for x in os.environ.get("OWNER_IDS", "5296584067,5364178811").split(',')]
THUMBNAIL = os.environ.get("THUMBNAIL", "Assist/Images/thumbnail.jpg")
STICKER_ID = os.environ.get("STICKER_ID", "CAACAgUAAxkBAAIJZGfLOdpxPmkKJ_nlJICh0bmi7GF1AALLFwACWARYVg4ubUgM9uuVNgQ")
PORT = os.environ.get("PORT", "8080")
TG_BOT_WORKERS = int(os.environ.get("TG_BOT_WORKERS", "1"))

# Aria2 RPC configuration
ARIA2_SECRET = os.environ.get("ARIA2_SECRET", "")  # Optional: Use "" if no secret is set
ARIA2_HOST = os.environ.get("ARIA2_HOST", "http://localhost")  # Default host
ARIA2_PORT = int(os.environ.get("ARIA2_PORT", "6800"))  # Default port

# Logging Channel Configuration
# Replace None with your log channel ID when you have one
# Example: LOG_CHANNEL = -1001234567890
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-1002197279542"))

# Post Format
POST_FORMAT = """
{title}\n\n
• EPISODE: {episode}
• GENRAS: {genras}
• RATING: {rating}

•SYPNOSYS:
{description}
"""

# Logging Configuration
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

# Set Pyrogram logging level to WARNING to reduce noise
logging.getLogger("pyrogram").setLevel(logging.WARNING)

def LOGGER(name: str) -> logging.Logger:
    """
    Returns a logger instance that will be used throughout the application.
    Args:
        name (str): The name of the logger, typically __name__ of the module.
    Returns:
        logging.Logger: A configured logger instance.
    """
    return logging.getLogger(name)