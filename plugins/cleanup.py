import os
import logging
from pyrogram import filters
from bot import Bot
from config import OWNER_IDS, LOG_FILE_NAME
from .video_handler import user_data, logger

def cleanup(user_id):
    if user_id in user_data:
        data = user_data[user_id]
        for key in ["video", "subtitle"]:
            if key in data and os.path.exists(data[key]):
                os.remove(data[key])
        user_data.pop(user_id, None)
        logger.info(f"Cleaned up data for user {user_id}")

@Bot.on_message(filters.user(OWNER_IDS) & filters.command("cleanup"), group=0)
async def clear_storage(client, message):
    user_id = message.from_user.id
    cleanup(user_id)
    await message.reply("Storage has been cleared.")

@Bot.on_message(filters.user(OWNER_IDS) & filters.command("logs"))
async def get_log_file(client, message):
    try:
        await message.reply_document(document=LOG_FILE_NAME, caption="log file by SubMerger")
    except Exception as e:
        logger.error(f"Failed to send log file to OWNER: {e}")
        await message.reply(f"Error:{e}")
