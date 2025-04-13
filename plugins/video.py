import os
import subprocess
import logging
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from asyncio import create_task
from bot import Bot
from config import OWNER_ID, LOG_FILE_NAME, OWNER_IDS
import asyncio

# Temporary storage for user progress and file paths
user_data = {}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Enhanced progress bar for Telegram
async def progress_bar(current, total, status_msg, action="Processing"):
    try:
        progress_percent = (current / total) * 100
        bar_length = 20
        filled_length = int(bar_length * current // total)
        bar = "█" * filled_length + "-" * (bar_length - filled_length)
        progress_text = f"{action}...\n[{bar}] {progress_percent:.2f}%\n({current // (1024 ** 2)} MB / {total // (1024 ** 2)} MB)"
        await status_msg.edit_text(progress_text)
    except Exception as e:
        logger.error(f"Failed to update progress bar: {e}")
        try:
            await status_msg.edit_text(f"Error during {action.lower()} progress: {e}")
        except:
            pass

# Log file get handler
@Bot.on_message(filters.user(OWNER_IDS) & filters.command("logs"))
async def get_log_file(client, message):
    try:
        await message.reply_document(document=LOG_FILE_NAME, caption="log file by SubMerger")
    except Exception as e:
        logger.error(f"Failed to send log file to OWNER: {e}")
        await message.reply(f"Error:{e}")

@Bot.on_message(filters.user(OWNER_IDS) & filters.command("final"), group=0)
async def start_conversion(client, message):
    await message.reply("Send me the subtitle file (.srt or .vtt) for conversion.")

# Command to clear full storage
@Bot.on_message(filters.user(OWNER_IDS) & filters.command("cleanup"), group=0)
async def clear_storage(client, message):
    user_id = message.from_user.id
    cleanup(user_id)
    await message.reply("Storage has been cleared.")

# Subtitle Upload Handler
@Bot.on_message(
    filters.user(OWNER_IDS) &
    filters.document & filters.create(lambda _, __, m: m.document and m.document.file_name.endswith((".srt", ".vtt")))
)
async def handle_subtitle_conversion(client, message):
    user_id = message.from_user.id
    try:
        status_msg = await message.reply("Preparing to download subtitle...")
        loop = asyncio.get_event_loop()
        subtitle_file = await message.download(
            file_name=f"sub_{user_id}.ass",
            progress=lambda current, total: asyncio.run_coroutine_threadsafe(
                progress_bar(current, total, status_msg, action="Downloading Subtitle"), loop
            )
        )
        logger.info(f"Subtitle downloaded: {subtitle_file}")

        # Convert SRT and VTT to ASS
        ass_file = subtitle_file.rsplit('.', 1)[0] + ".ass"
        ffmpeg_cmd = ["ffmpeg", "-i", subtitle_file, ass_file]
        subprocess.run(ffmpeg_cmd, check=True)
        os.remove(subtitle_file)  # Remove original SRT or VTT file

        # Modify the .ass file
        with open(ass_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        modified_lines = []
        for line in lines:
            if line.startswith("Style: Default"):
                line = line.replace("Arial", "Oath-Bold").replace(",16,", ",20,")
            if line.startswith("Dialogue:"):
                parts = line.split(",", 9)  # Ensure the dialogue part is modified
                if len(parts) > 9:
                    parts[9] = f"{{\\pos(193,265)}}{parts[9]}"
                line = ",".join(parts)
            modified_lines.append(line)

        with open(ass_file, "w", encoding="utf-8") as f:
            f.writelines(modified_lines)

        logger.info(f"Modified subtitle file: {ass_file}")

        # Send the modified subtitle file to the user
        await message.reply_document(document=ass_file, caption="Here is the converted and modified subtitle file.")
    except Exception as e:
        logger.error(f"Subtitle conversion failed: {e}")
        await message.reply(f"Error during subtitle conversion: {e}")

@Bot.on_message(filters.user(OWNER_IDS) & filters.command("merge"), group=0)
async def start(client, message):
    await message.reply("Send me a video file (MKV or MP4) to add subtitles.")

# Video Upload Handler
@Bot.on_message(
    filters.user(OWNER_IDS) &
    (filters.video | (filters.document & filters.create(lambda _, __, m: m.document and (m.document.file_name.endswith((".mp4", ".mkv")) or not os.path.splitext(m.document.file_name)[1]))))
)
async def handle_video(client, message):
    user_id = message.from_user.id
    file_name = message.video.file_name if message.video else message.document.file_name

    logger.info(f"Receiving video: {file_name} from {user_id}")

    try:
        status_msg = await message.reply("Preparing to download...")

        # Download video with progress bar
        loop = asyncio.get_event_loop()
        video_file = await message.download(
            file_name=f"vid_{user_id}.tmp",
            progress=lambda current, total: asyncio.run_coroutine_threadsafe(
                progress_bar(current, total, status_msg, action="Downloading Video"), loop
            )
        )

        if user_id not in user_data:
            user_data[user_id] = {}

        user_data[user_id]["video"] = video_file
        user_data[user_id]["step"] = "video"

        # Send buttons to user
        buttons = [
            [InlineKeyboardButton("Merge", callback_data=f"merge_{user_id}")],
            [InlineKeyboardButton("Extract Sub", callback_data=f"extract_{user_id}")],
            [InlineKeyboardButton("Generate Screenshot", callback_data=f"screenshot_{user_id}")]
        ]
        await status_msg.edit_text("Choose an action:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Failed to download video: {e}")
        await message.reply(f"Error during download: {e}")

# Handle button clicks
@Bot.on_callback_query(filters.regex(r"(merge|extract|screenshot)_(\d+)"))
async def handle_button_click(client, callback_query):
    action = callback_query.matches[0].group(1)
    user_id = int(callback_query.matches[0].group(2))

    if action == "merge":
        await callback_query.message.reply("Send the subtitle file (.ass) to merge.")
    elif action == "extract":
        await extract_subtitles(client, callback_query.message, user_id)
    elif action == "screenshot":
        await generate_screenshot(client, callback_query.message, user_id)

# Merging Subtitles
async def merge_subtitles_task(client, message, user_id):
    data = user_data[user_id]
    video = data["video"]
    subtitle = data["subtitle"]
    new_name = data["new_name"]
    caption = data["caption"]
    output_file = f"{new_name}.mkv"

    try:
        status_msg = await message.reply("Merging subtitles...")
        ffmpeg_cmd = ["ffmpeg", "-i", video, "-i", subtitle, "-c", "copy", "-y", output_file]
        process = await asyncio.create_subprocess_exec(*ffmpeg_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.wait()

        # Upload merged video
        await upload_with_progress(client, message.chat.id, output_file, f"Here is your merged video: {output_file}")
    except Exception as e:
        logger.error(f"Failed to merge subtitles: {e}")
        await message.reply(f"Error during merging: {e}")
    finally:
        cleanup(user_id)

# Upload with Progress
async def upload_with_progress(client, chat_id, file_path, caption):
    try:
        status_msg = await client.send_message(chat_id, "Preparing to upload...")
        loop = asyncio.get_event_loop()
        await client.send_document(
            chat_id=chat_id,
            document=file_path,
            caption=caption,
            progress=lambda current, total: asyncio.run_coroutine_threadsafe(
                progress_bar(current, total, status_msg, action="Uploading File"), loop
            )
        )
        await status_msg.delete()
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        await client.send_message(chat_id, f"Error during upload: {e}")

# Cleanup function
def cleanup(user_id):
    if user_id in user_data:
        data = user_data[user_id]
        for key in ["video", "subtitle"]:
            if key in data and os.path.exists(data[key]):
                os.remove(data[key])
        user_data.pop(user_id, None)