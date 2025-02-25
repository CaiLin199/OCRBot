import os
import subprocess
import logging
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from asyncio import create_task
from bot import Bot
from config import OWNER_ID

# Temporary storage for user progress and file paths
user_data = {}

# Configure logging
logging.basicConfig(level=logging.INFO)

@Bot.on_message(filters.user(OWNER_ID) & filters.command("final"), group=0)
async def start_conversion(client, message):
    await message.reply("Send me the subtitle file (.srt or .vtt) for conversion.")

# Function to extract timestamps from subtitles
def extract_timestamps(subtitle_file):
    timestamps = []
    with open(subtitle_file, "r", encoding="utf-8") as file:
        for line in file:
            if '-->' in line:
                timestamps.append(line.strip().split(' --> ')[0])  # Get start time of subtitle
    return timestamps

# Function to extract screenshot with one subtitle line rendered
def extract_screenshot(video_path, subtitle_path, timestamp, output_image):
    command = [
        'ffmpeg',
        '-ss', timestamp,
        '-i', video_path,
        '-vf', f'subtitles={subtitle_path}',
        '-frames:v', '1',
        '-q:v', '2',
        output_image
    ]
    subprocess.run(command, check=True)

# Function to clean up user data and files
def cleanup(user_id):
    if user_id in user_data:
        data = user_data[user_id]
        for key in ["video", "subtitle"]:
            if key in data and os.path.exists(data[key]):
                os.remove(data[key])
        user_data.pop(user_id, None)

# Subtitle Upload Handler
@Bot.on_message(
    filters.user(OWNER_ID) &
    filters.document & filters.create(lambda _, __, m: m.document and m.document.file_name.endswith((".srt", ".vtt")))
)
async def handle_subtitle_conversion(client, message):
    user_id = message.from_user.id
    subtitle_file = await message.download()

    logging.info(f"Subtitle downloaded: {subtitle_file}")

    # Extract timestamps from subtitles
    timestamps = extract_timestamps(subtitle_file)
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["timestamps"] = timestamps

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

    logging.info(f"Modified subtitle file: {ass_file}")

    # Send the modified subtitle file to the user
    await message.reply_document(document=ass_file, caption="Here is the converted and modified subtitle file.")

@Bot.on_message(filters.user(OWNER_ID) & filters.command("start"), group=0)
async def start(client, message):
    await message.reply("Send me a video file (MKV or MP4) to add subtitles.")

# Video Upload Handler
@Bot.on_message(
    filters.user(OWNER_ID) &
    (filters.video | (filters.document & filters.create(lambda _, __, m: m.document and (m.document.file_name.endswith((".mp4", ".mkv")) or not os.path.splitext(m.document.file_name)[1]))))
)
async def handle_video(client, message):
    user_id = message.from_user.id
    file_name = message.video.file_name if message.video else message.document.file_name

    # Ensure extension is present
    if not os.path.splitext(file_name)[1]:
        file_name += ".mp4"

    file_size = message.video.file_size if message.video else message.document.file_size

    logging.info(f"Receiving video: {file_name} ({file_size / (1024*1024):.2f} MB) from {user_id}")

    async def progress_log(current, total):
        percent = (current / total) * 100
        logging.info(f"Downloading: {current / (1024*1024):.2f}/{total / (1024*1024):.2f} MB ({percent:.2f}%) for user {user_id}")

    video_file = await message.download(file_name=file_name, progress=progress_log)

    if video_file.endswith(".mp4"):
        new_video_file = video_file.replace(".mp4", ".mkv")
        ffmpeg_cmd = ["ffmpeg", "-i", video_file, "-c", "copy", new_video_file]
        subprocess.run(ffmpeg_cmd, check=True)
        os.remove(video_file)
        video_file = new_video_file

    logging.info(f"Download complete: {video_file}")

    if user_id not in user_data:
        user_data[user_id] = {}

    user_data[user_id]["video"] = video_file
    user_data[user_id]["step"] = "video"
    await message.reply("Video received! Now send the subtitle file (.ass).")

# Subtitle Upload Handler
@Bot.on_message(
    filters.user(OWNER_ID) &
    filters.document & filters.create(lambda _, __, m: m.document and m.document.file_name.endswith(".ass"))
)
async def handle_subtitle(client, message):
    user_id = message.from_user.id
    subtitle_file = await message.download()

    logging.info(f"Subtitle downloaded: {subtitle_file}")

    # Store subtitle file and wait for new name
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["subtitle"] = subtitle_file
    user_data[user_id]["step"] = "subtitle"
    await message.reply("Subtitle received! Now send the new name for the output file (without extension).")

# Handle Filename & Caption
@Bot.on_message(filters.user(OWNER_ID) & filters.text)
async def handle_name_or_caption(client, message):
    user_id = message.from_user.id

    logging.info(f"Receiving new filename from {user_id}")

    if user_id in user_data and user_data[user_id].get("step") == "subtitle":
        new_name = message.text.strip()

        user_data[user_id]["new_name"] = new_name
        user_data[user_id]["caption"] = new_name
        user_data[user_id]["step"] = "name"
        await message.reply("New name and caption received! Now processing the video.")
        create_task(merge_subtitles_task(client, message, user_id))  # Ensure the task is created here
    else:
        await message.reply("Please start by sending a video file.")

# Merging Subtitles
async def merge_subtitles_task(client, message, user_id):
    data = user_data[user_id]
    video = data["video"]
    subtitle = data["subtitle"]
    new_name = data["new_name"]
    caption = data["caption"]
    output_file = f"{new_name}.mkv"

    font = 'Assist/Font/OathBold.otf'
    thumbnail = 'Assist/Images/thumbnail.jpg'

    ffmpeg_cmd = [
        "ffmpeg", "-i", video, "-i", subtitle,
        "-attach", font, "-metadata:s:t:0", "mimetype=application/x-font-otf",
        "-map", "0", "-map", "1",
        "-metadata:s:s:0", "title=HeavenlySubs",
        "-metadata:s:s:0", "language=eng", "-disposition:s:s:0", "default",
        "-c", "copy", output_file
    ]

    try:
        logging.info(f"Merging subtitles for user {user_id}: {output_file}")
        subprocess.run(ffmpeg_cmd, check=True)

        async def upload_progress(current, total):
            percent = (current / total) * 100
            logging.info(f"Uploading: {current / (1024*1024):.2f}/{total / (1024*1024):.2f} MB ({percent:.2f}%) for user {user_id}")

        logging.info(f"Uploading merged video: {output_file}")
        await message.reply_document(
            document=output_file,
            caption=caption,
            thumb=thumbnail,
            progress=upload_progress,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Get Screenshot", callback_data=f"screenshot_{user_id}_{new_name}")]]
            )
        )

    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to merge subtitles: {e}")
        await message.reply(f"Error: {e}")

# Handle Screenshot Button Click
@Bot.on_callback_query(filters.regex(r"screenshot_(\d+)_(.+)"))
async def handle_screenshot(client, callback_query):
    user_id = int(callback_query.matches[0].group(1))
    new_name = callback_query.matches[0].group(2)

    if user_id in user_data and "video" in user_data[user_id] and "subtitle" in user_data[user_id] and "timestamps" in user_data[user_id]:
        video = user_data[user_id]["video"]
        subtitle = user_data[user_id]["subtitle"]
        timestamps = user_data[user_id]["timestamps"]

        # Extract screenshot at the first subtitle timestamp
        timestamp = timestamps[0]  # Using only the first timestamp
        screenshot_path = f"{new_name}_screenshot_1.png"
        extract_screenshot(video, subtitle, timestamp, screenshot_path)

        # Send the screenshot
        await callback_query.message.reply_photo(photo=screenshot_path, caption="Here is a screenshot with subtitles.")
        os.remove(screenshot_path)  # Clean up after sending

        # Clean up user data and files
        cleanup(user_id)
    else:
        await callback_query.message.reply("Unable to find video and subtitle data. Please try again.")

# Command to clear full storage
@Bot.on_message(filters.user(OWNER_ID) & filters.command("cleanup"), group=0)
async def clear_storage(client, message):
    user_id = message.from_user.id
    if user_id in user_data:
        cleanup(user_id)
        await message.reply("Storage has been cleared.")
    else:
        await message.reply("No storage to clear.")