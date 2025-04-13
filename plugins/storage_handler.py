import os
from pyrogram import filters
from bot import Bot
from config import OWNER_IDS
import logging

logger = logging.getLogger(__name__)

# Temporary storage for user progress and file paths
user_data = {}

# Command to clear full storage
@Bot.on_message(filters.user(OWNER_IDS) & filters.command("cleanup"), group=0)
async def clear_storage(client, message):
    user_id = message.from_user.id
    cleanup(user_id)
    await message.reply("Storage has been cleared.")

# Cleanup function
def cleanup(user_id):
    if user_id in user_data:
        data = user_data[user_id]
        for key in ["video", "subtitle"]:
            if key in data and os.path.exists(data[key]):
                os.remove(data[key])
        user_data.pop(user_id, None)
        logger.info(f"Cleaned up data for user {user_id}")