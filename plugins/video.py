import os
import asyncio
import logging
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from queue import Queue
import ffmpeg
import psutil
from bot import Bot
from config import OWNER_IDS, LOG_FILE_NAME

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - [%(message)s]')
logger = logging.getLogger(__name__)

# Task queue for FFmpeg operations
task_queue = Queue()

# Temporary storage for user data
user_data = {}

# Resource monitoring function
def log_resources(prefix=""):
    ram = psutil.virtual_memory().percent
    storage = psutil.disk_usage("/").used / (1024 ** 3)  # GB
    cpu = psutil.cpu_percent(interval=None)
    return f"{prefix}RAM: {ram:.1f}% | Storage: {storage:.2f}GB | CPU: {cpu:.1f}%"

# Log file handler
@Bot.on_message(filters.user(OWNER_IDS) & filters.command("logs"))
async def get_log_file(client, message):
    try:
        await message.reply_document(document=LOG_FILE_NAME, caption="Log file by SubMerger")
        logger.info(log_resources("Sent log file: "))
    except Exception as e:
        logger.error(f"Failed to send log file: {e}")
        await message.reply(f"Error: {e}")

@Bot.on_message(filters.user(OWNER_IDS) & filters.command("final"))
async def start_conversion(client, message):
    await message.reply("Send a subtitle file (.srt or .vtt) for conversion.")

@Bot.on_message(filters.user(OWNER_IDS) & filters.command("cleanup"))
async def clear_storage(client, message):
    user_id = message.from_user.id
    await cleanup(user_id)
    await message.reply("Storage cleared.")
    logger.info(log_resources(f"Cleared storage for user {user_id}: "))

# Enhanced progress bar for Telegram
async def progress_bar(current, total, status_msg, action="Processing"):
    try:
        # Calculate progress
        progress_percent = (current / total) * 100
        bar_length = 20  # Length of the progress bar
        filled_length = int(bar_length * current // total)
        bar = "█" * filled_length + "-" * (bar_length - filled_length)
        progress_text = f"{action}...\n[{bar}] {progress_percent:.2f}%\n{current // (1024**2)} MB / {total // (1024**2)} MB"

        # Edit the message with the progress bar
        await status_msg.edit_text(progress_text)
    except Exception as e:
        logger.error(f"Failed to update progress bar: {e}")
        try:
            await status_msg.edit_text(f"Error during {action.lower()} progress: {e}")
        except:
            pass  # Avoid crashing if edit_text fails

@Bot.on_message(
    filters.user(OWNER_IDS) &
    (filters.video | (filters.document & filters.create(lambda _, __, m: m.document and (m.document.file_name.endswith((".mp4", ".mkv")) or not os.path.splitext(m.document.file_name)[1]))))
)
async def handle_video(client, message):
    user_id = message.from_user.id
    file_name = message.video.file_name if message.video else message.document.file_name
    file_size = message.video.file_size if message.video else message.document.file_size

    if file_size > 650_000_000:  # Cap at ~650 MB
        await message.reply("Video too large, please send under 650 MB.")
        return

    try:
        # Initial progress message
        status_msg = await message.reply("Preparing to download...")

        # Download the video with a progress bar
        loop = asyncio.get_event_loop()
        video_file = await message.download(
            file_name=f"vid_{user_id}.tmp",
            progress=lambda current, total: asyncio.run_coroutine_threadsafe(
                progress_bar(current, total, status_msg, action="Downloading"), loop
            )
        )
        logger.info(log_resources(f"Download complete ({video_file}): "))

        # Save the downloaded video in user data
        user_data[user_id] = {"video": video_file, "step": "video"}

        # Display available actions
        buttons = [
            [InlineKeyboardButton("Merge", callback_data=f"merge_{user_id}")],
            [InlineKeyboardButton("Extract Sub", callback_data=f"extract_{user_id}")],
            [InlineKeyboardButton("Generate Screenshot", callback_data=f"screenshot_{user_id}")]
        ]
        await status_msg.edit_text("Choose an action:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Video download failed: {e}")
        await status_msg.edit_text(f"Error during download: {e}")

@Bot.on_message(filters.user(OWNER_IDS) & filters.document & filters.regex(r"\.ass$"))
async def handle_subtitle(client, message):
    user_id = message.from_user.id
    try:
        status_msg = await message.reply("Preparing to download subtitle...")
        loop = asyncio.get_event_loop()
        subtitle_file = await message.download(
            file_name=f"sub_{user_id}.ass",
            progress=lambda current, total: asyncio.run_coroutine_threadsafe(
                progress_bar(current, total, status_msg, action="Downloading"), loop
            )
        )
        logger.info(log_resources(f"Subtitle downloaded ({subtitle_file}): "))

        user_data[user_id]["subtitle"] = subtitle_file
        user_data[user_id]["step"] = "subtitle"
        await status_msg.edit_text("Send the output file name (without extension).")
    except Exception as e:
        logger.error(f"Subtitle upload failed: {e}")
        await status_msg.edit_text(f"Error during subtitle download: {e}")

# Cleanup function
async def cleanup(user_id):
    if user_id in user_data:
        for key in ["video", "subtitle"]:
            if key in user_data[user_id] and os.path.exists(user_data[user_id][key]):
                os.remove(user_data[user_id][key])
        user_data.pop(user_id, None)
        logger.info(log_resources(f"Cleaned up for user {user_id}: "))