import os
import subprocess
import logging
from pyrogram import filters
from asyncio import create_task
from bot import Bot  # Assuming Bot is a properly initialized Pyrogram Client in bot.py
from config import OWNER_ID, KOYEB_LOG_FILE  # OWNER_ID and KOYEB_LOG_FILE should be defined in config.py

# Temporary storage for user progress and file paths
user_data = {}

# List of restricted words (commands like start, logs) to avoid conflicts with filenames or captions
restricted_keywords = ["start", "logs", "help", "about", "commands", "status"]

# Configure logging
logging.basicConfig(level=logging.INFO)

# Function to check if the filename or caption contains any restricted keywords
def contains_restricted_keywords(text):
    return any(keyword.lower() in text.lower() for keyword in restricted_keywords)

# Handle video upload
@Bot.on_message(
    filters.user(OWNER_ID) &
    (filters.video | (filters.document & filters.create(lambda _, __, m: m.document and m.document.file_name.endswith((".mkv", ".mp4")))))
)
async def handle_video(client, message):
    user_id = message.from_user.id

    logging.info(f"Received video from {user_id}")

    # Download and store video
    video_file = await message.download()
    user_data[user_id] = {"video": video_file, "step": "video"}
    await message.reply("Video received! Now send the subtitle file (.ass or .srt).")

# Handle subtitle file upload
@Bot.on_message(
    filters.user(OWNER_ID) &
    filters.document & filters.create(lambda _, __, m: m.document and m.document.file_name.endswith((".ass", ".srt")))
)
async def handle_subtitle(client, message):
    user_id = message.from_user.id

    logging.info(f"Received subtitle from {user_id}")

    if user_id in user_data and user_data[user_id].get("step") == "video":
        # Download and store subtitle
        subtitle_file = await message.download()
        user_data[user_id]["subtitle"] = subtitle_file
        user_data[user_id]["step"] = "subtitle"
        await message.reply("Subtitle received! Now send the new name for the output file (without extension).")
    else:
        await message.reply("Please send a video file first.")

# Handle new name and caption input
@Bot.on_message(filters.user(OWNER_ID) & filters.text)
async def handle_name_or_caption(client, message):
    user_id = message.from_user.id

    logging.info(f"Received name or caption from {user_id}")

    if user_id in user_data:
        step = user_data[user_id].get("step")
        if step == "subtitle":
            new_name = message.text.strip()

            # Check if new name or caption contains restricted keywords
            if contains_restricted_keywords(new_name):
                await message.reply("The name or caption you provided contains restricted keywords. Please choose a different name.")
                return

            user_data[user_id]["new_name"] = new_name
            user_data[user_id]["caption"] = new_name  # Name and caption are now the same
            user_data[user_id]["step"] = "name"
            await message.reply("New name and caption received! Now send a thumbnail image (JPG or PNG).")
    else:
        await message.reply("Please start by sending a video file.")

# Handle thumbnail upload
@Bot.on_message(filters.user(OWNER_ID) & filters.photo)
async def handle_thumbnail(client, message):
    user_id = message.from_user.id

    logging.info(f"Received thumbnail from {user_id}")

    if user_id in user_data and user_data[user_id].get("step") == "name":
        thumbnail_file = await message.download()
        user_data[user_id]["thumbnail"] = thumbnail_file

        # Start merging
        await message.reply("Thumbnail received! Merging subtitles into the video...")
        create_task(merge_subtitles_task(client, message, user_id))  # Offload processing to a background task
    else:
        await message.reply("Please send a name first.")

# Background task to handle merging subtitles
async def merge_subtitles_task(client, message, user_id):
    data = user_data[user_id]
    video = data["video"]
    subtitle = data["subtitle"]
    new_name = data["new_name"]
    caption = data["caption"]
    thumbnail = data["thumbnail"]
    output_file = f"{new_name}.mkv"

    # Correct path to font file in the GitHub repo (relative to the repo structure)
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
        # Run ffmpeg command
        subprocess.run(ffmpeg_cmd, check=True)
        await message.reply_document(
            document=output_file,
            caption=caption,
            thumb=thumbnail
        )  # Send document with caption and thumbnail
    except subprocess.CalledProcessError as e:
        await message.reply(f"Failed to merge subtitles: {e}")
    finally:
        # Clean up files and data
        os.remove(video)
        os.remove(subtitle)
        os.remove(thumbnail)
        if os.path.exists(output_file):
            os.remove(output_file)
        user_data.pop(user_id, None)

# Command to start the bot interaction
@Bot.on_message(filters.user(OWNER_ID) & filters.command("start"))
async def start(client, message):
    await message.reply("Welcome! Start by sending me a video file (MKV or MP4) to add subtitles.")

# Command to fetch logs from Koyeb
@Bot.on_message(filters.user(OWNER_ID) & filters.command("logs"))
async def fetch_logs(client, message):
    # Path to your Koyeb log file (update KOYEB_LOG_FILE in config.py)
    try:
        with open(KOYEB_LOG_FILE, 'r') as log_file:
            logs = log_file.read()
            await message.reply(f"Latest logs:\n\n{logs}")
    except Exception as e:
        await message.reply(f"Error fetching logs: {str(e)}")
