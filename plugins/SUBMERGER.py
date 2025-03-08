import os
import subprocess
import logging
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from asyncio import create_task
from bot import Bot
from config import OWNER_ID, LOG_FILE_NAME, OWNER_IDS

# Temporary storage for user progress and file paths
user_data = {}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    subtitle_file = await message.download()

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

        # Send buttons to user
        buttons = [
            [InlineKeyboardButton("Merge", callback_data=f"merge_{user_id}")],
            [InlineKeyboardButton("Extract Sub", callback_data=f"extract_{user_id}")],
            [InlineKeyboardButton("Generate Screenshot", callback_data=f"screenshot_{user_id}")]
        ]
        await message.reply("Choose an action:", reply_markup=InlineKeyboardMarkup(buttons))
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

# Subtitle Upload Handler
@Bot.on_message(
    filters.user(OWNER_IDS) &
    filters.document & filters.create(lambda _, __, m: m.document and m.document.file_name.endswith(".ass"))
)
async def handle_subtitle(client, message):
    user_id = message.from_user.id
    subtitle_file = await message.download()

    logger.info(f"Subtitle downloaded: {subtitle_file}")

    # Ensure user_data entry exists for the user
    if user_id not in user_data:
        user_data[user_id] = {}

    # Store subtitle file
    user_data[user_id]["subtitle"] = subtitle_file
    user_data[user_id]["step"] = "subtitle"
    await message.reply("Subtitle received! Now send the new name for the output file (without extension).")

# Handle Filename & Caption
@Bot.on_message(filters.user(OWNER_IDS) & filters.text)
async def handle_name_or_caption(client, message):
    user_id = message.from_user.id

    logger.info(f"Receiving new filename from {user_id}")

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
        "ffmpeg", "-i", video,
        "-map", "0:v", "-map", "0:a?",  # Map video and audio only, excluding existing subtitles
        "-i", subtitle,
        "-attach", font, "-metadata:s:t:0", "mimetype=application/x-font-otf",
        "-map", "1",
        "-metadata:s:s:0", "title=HeavenlySubs",
        "-metadata:s:s:0", "language=eng", "-disposition:s:s:0", "default",
        "-c", "copy", output_file
    ]

    try:
        logger.info(f"Merging subtitles for user {user_id}: {output_file}")
        subprocess.run(ffmpeg_cmd, check=True)

        async def upload_progress(current, total):
            percent = (current / total) * 100
            logger.info(f"Uploading: {current / (1024*1024):.2f}/{total / (1024*1024):.2f} MB ({percent:.2f}%) for user {user_id}")

        logger.info(f"Uploading merged video: {output_file}")
        await message.reply_document(
            document=output_file,
            caption=caption,
            thumb=thumbnail,
            progress=upload_progress
        )

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to merge subtitles: {e}")
        await message.reply(f"Error: {e}")
    finally:
        cleanup(user_id)

# Function to extract subtitles using ffmpeg
async def extract_subtitles(client, message, user_id):
    data = user_data[user_id]
    video_file = data["video"]
    output_subtitle = video_file.rsplit('.', 1)[0] + ".srt"
    output_ass = video_file.rsplit('.', 1)[0] + ".ass"

    ffmpeg_cmd = ["ffmpeg", "-i", video_file, "-map", "0:s:0", output_subtitle]

    try:
        logger.info(f"Extracting subtitles from {video_file}")
        subprocess.run(ffmpeg_cmd, check=True)
        logger.info(f"Subtitles extracted to {output_subtitle}")

        # Convert SRT to ASS format
        ffmpeg_cmd_ass = ["ffmpeg", "-i", output_subtitle, output_ass]
        subprocess.run(ffmpeg_cmd_ass, check=True)
        logger.info(f"Subtitles converted to {output_ass}")

        await message.reply_document(document=output_subtitle, caption="Here is the extracted subtitle file.")
        await message.reply_document(document=output_ass, caption="Here is the converted ASS subtitle file.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to extract subtitles: {e}")
        await message.reply(f"Error: {e}")

# Function to generate screenshot using ffmpeg
async def generate_screenshot(client, message, user_id):
    data = user_data[user_id]
    video_file = data["video"]
    screenshot_path = video_file.rsplit('.', 1)[0] + "_screenshot.png"
    timestamp = "00:00:05"  # Example timestamp, you can modify as needed

    ffmpeg_cmd = [
        "ffmpeg", "-ss", timestamp, "-i", video_file,
        "-frames:v", "1", "-q:v", "2",
        screenshot_path
    ]

    try:
        logger.info(f"Generating screenshot from {video_file} at {timestamp}")
        subprocess.run(ffmpeg_cmd, check=True)
        logger.info(f"Screenshot saved to {screenshot_path}")

        await message.reply_photo(photo=screenshot_path, caption="Here is the screenshot.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to generate screenshot: {e}")
        await message.reply(f"Error: {e}")

# Function to clean up user data and files
def cleanup(user_id):
    if user_id in user_data:
        data = user_data[user_id]
        for key in ["video", "subtitle"]:
            if key in data and os.path.exists(data[key]):
                os.remove(data[key])
        user_data.pop(user_id, None)
        logger.info(f"Cleaned up data for user {user_id}")