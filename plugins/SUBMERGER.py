import os
import subprocess
import logging
from pyrogram import filters
from asyncio import create_task
from bot import Bot  # Assuming Bot is a properly initialized Pyrogram Client in bot.py
from config import OWNER_ID, LOG_FILE_NAME  

# Temporary storage for user progress and file paths
user_data = {}

# List of restricted words (commands to ignore as filenames)
restricted_keywords = ["start", "logs"]

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def contains_restricted_keywords(text):
    return any(keyword.lower() in text.lower() for keyword in restricted_keywords)

@Bot.on_message(
    filters.user(OWNER_ID) &
    (filters.video | (filters.document & filters.create(lambda _, __, m: m.document and m.document.file_name.endswith((".mkv", ".mp4")))))
)
async def handle_video(client, message):
    user_id = message.from_user.id
    file_name = message.video.file_name if message.video else message.document.file_name
    file_size = message.video.file_size if message.video else message.document.file_size

    logging.info(f"Receiving video: {file_name} ({file_size / (1024*1024):.2f} MB) from {user_id}")

    # Download video
    video_file = await message.download(progress=progress_log, user_id=user_id, stage="Downloading")
    
    # Convert MP4 to MKV if needed
    if video_file.endswith(".mp4"):
        mkv_file = video_file.replace(".mp4", ".mkv")
        logging.info(f"Converting {video_file} to MKV format...")
        subprocess.run(["ffmpeg", "-i", video_file, "-c", "copy", mkv_file], check=True)
        os.remove(video_file)
        video_file = mkv_file

    user_data[user_id] = {"video": video_file, "step": "video"}
    await message.reply("Video received! Now send the subtitle file (.ass or .srt).")

@Bot.on_message(
    filters.user(OWNER_ID) &
    filters.document & filters.create(lambda _, __, m: m.document and m.document.file_name.endswith((".ass", ".srt")))
)
async def handle_subtitle(client, message):
    user_id = message.from_user.id
    file_name = message.document.file_name
    file_size = message.document.file_size

    logging.info(f"Receiving subtitle: {file_name} ({file_size / (1024*1024):.2f} MB) from {user_id}")

    if user_id in user_data and user_data[user_id].get("step") == "video":
        subtitle_file = await message.download(progress=progress_log, user_id=user_id, stage="Downloading")
        user_data[user_id]["subtitle"] = subtitle_file
        user_data[user_id]["step"] = "subtitle"
        await message.reply("Subtitle received! Now send the new name for the output file (without extension).")
    else:
        await message.reply("Please send a video file first.")

@Bot.on_message(filters.user(OWNER_ID) & filters.text)
async def handle_name_or_caption(client, message):
    user_id = message.from_user.id
    new_name = message.text.strip()

    logging.info(f"Receiving new filename: {new_name} from {user_id}")

    if contains_restricted_keywords(new_name):
        await message.reply("Invalid name. Choose a different name.")
        return

    if user_id in user_data and user_data[user_id].get("step") == "subtitle":
        user_data[user_id]["new_name"] = new_name
        user_data[user_id]["caption"] = new_name
        user_data[user_id]["step"] = "name"
        await message.reply("New name received! Now send a thumbnail image (JPG or PNG).")
    else:
        await message.reply("Please send a video file first.")

@Bot.on_message(filters.user(OWNER_ID) & filters.photo)
async def handle_thumbnail(client, message):
    user_id = message.from_user.id

    logging.info(f"Receiving thumbnail from {user_id}")

    if user_id in user_data and user_data[user_id].get("step") == "name":
        thumbnail_file = await message.download(progress=progress_log, user_id=user_id, stage="Downloading")
        user_data[user_id]["thumbnail"] = thumbnail_file
        await message.reply("Thumbnail received! Merging subtitles into the video...")

        create_task(merge_subtitles_task(client, message, user_id))
    else:
        await message.reply("Please send a name first.")

async def merge_subtitles_task(client, message, user_id):
    data = user_data[user_id]
    video = data["video"]
    subtitle = data["subtitle"]
    new_name = data["new_name"]
    caption = data["caption"]
    thumbnail = data["thumbnail"]
    output_file = f"{new_name}.mkv"
    font = 'Assist/Font/OathBold.otf'

    ffmpeg_cmd = [
        "ffmpeg", "-i", video, "-i", subtitle,
        "-attach", font, "-metadata:s:t:0", "mimetype=application/x-font-otf",
        "-map", "0", "-map", "1",
        "-metadata:s:s:0", "title=DonghuaWillow",
        "-metadata:s:s:0", "language=eng", "-disposition:s:s:0", "default",
        "-c", "copy", output_file
    ]

    try:
        logging.info(f"Starting subtitle merge for {video}")
        subprocess.run(ffmpeg_cmd, check=True)
        logging.info(f"Subtitle merge completed: {output_file}")

        await message.reply("Uploading video...")
        await message.reply_document(
            document=output_file,
            caption=caption,
            thumb=thumbnail,
            progress=progress_log,
            user_id=user_id,
            stage="Uploading"
        )
        logging.info(f"Upload complete: {output_file}")

    except subprocess.CalledProcessError as e:
        logging.error(f"Error merging subtitles: {e}")
        await message.reply(f"Failed to merge subtitles: {e}")
    finally:
        os.remove(video)
        os.remove(subtitle)
        os.remove(thumbnail)
        if os.path.exists(output_file):
            os.remove(output_file)
        user_data.pop(user_id, None)

async def progress_log(current, total, user_id, stage):
    percent = (current / total) * 100
    logging.info(f"{stage}: {current / (1024*1024):.2f}/{total / (1024*1024):.2f} MB ({percent:.2f}%) for user {user_id}")

@Bot.on_message(filters.user(OWNER_ID) & filters.command("start"))
async def start(client, message):
    await message.reply("Welcome! Start by sending a video file (MKV or MP4) to add subtitles.")

@Bot.on_message(filters.user(OWNER_ID) & filters.command("logs"))
async def fetch_logs(client, message):
    try:
        with open(LOG_FILE_NAME, 'r') as log_file:
            logs = log_file.read()
            await message.reply(f"Latest logs:\n\n{logs}")
    except Exception as e:
        await message.reply(f"Error fetching logs: {str(e)}")
