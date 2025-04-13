import os
import logging
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot import Bot
from config import OWNER_IDS

# Shared user data dictionary
user_data = {}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@Bot.on_message(
    filters.user(OWNER_IDS) &
    (filters.video | (filters.document & filters.create(lambda _, __, m: m.document and (m.document.file_name.endswith((".mp4", ".mkv")) or not os.path.splitext(m.document.file_name)[1]))))
)
async def handle_video(client, message):
    user_id = message.from_user.id
    file_name = message.video.file_name if message.video else message.document.file_name

    logger.info(f"Receiving video: {file_name} from {user_id}")

    try:
        await message.reply("Video downloading...")

        async def progress_log(current, total):
            percent = (current / total) * 100
            logger.info(f"Downloading: {current / (1024*1024):.2f}/{total / (1024*1024):.2f} MB ({percent:.2f}%) for user {user_id}")

        video_file = await message.download(file_name=file_name, progress=progress_log)

        logger.info(f"Download complete: {video_file}")

        if user_id not in user_data:
            user_data[user_id] = {}

        user_data[user_id]["video"] = video_file
        user_data[user_id]["step"] = "video"

        buttons = [
            [InlineKeyboardButton("Merge", callback_data=f"merge_{user_id}")],
            [InlineKeyboardButton("Extract Sub", callback_data=f"extract_{user_id}")],
            [InlineKeyboardButton("Generate Screenshot", callback_data=f"screenshot_{user_id}")]
        ]
        await message.reply("Choose an action:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Failed to download video: {e}")
        await message.reply(f"Error during download: {e}")

@Bot.on_message(filters.user(OWNER_IDS) & filters.command("merge"), group=0)
async def start(client, message):
    await message.reply("Send me a video file (MKV or MP4) to add subtitles.")
