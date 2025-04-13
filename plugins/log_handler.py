import logging
from pyrogram import filters
from bot import Bot
from config import OWNER_IDS, LOG_FILE_NAME

logger = logging.getLogger(__name__)

# Log file get handler
@Bot.on_message(filters.user(OWNER_IDS) & filters.command("logs"))
async def get_log_file(client, message):
    try:
        await message.reply_document(document=LOG_FILE_NAME, caption="log file by SubMerger")
    except Exception as e:
        logger.error(f"Failed to send log file to OWNER: {e}")
        await message.reply(f"Error:{e}")