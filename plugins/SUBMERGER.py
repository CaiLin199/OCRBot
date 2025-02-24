import os
import subprocess
import logging
from pyrogram import filters
from asyncio import create_task
from bot import Bot
from config import OWNER_ID, LOG_FILE_NAME  

# Temporary storage for user progress and file paths
user_data = {}

# Configure logging
logging.basicConfig(level=logging.INFO)

@Bot.on_message(filters.user(OWNER_ID) & filters.command("start"), group=0)
async def start(client, message):
    await message.reply("Welcome! Send me a video file (MKV or MP4) to add subtitles.")

@Bot.on_message(filters.user(OWNER_ID) & filters.command("logs"), group=0)
async def fetch_logs(client, message):
    try:
        await message.reply_document(LOG_FILE_NAME, caption="Here are the latest logs.")
    except Exception as e:
        await message.reply(f"Error fetching logs: {str(e)}")


# Video Upload Handler
@Bot.on_message(
    filters.user(OWNER_ID) &
    (filters.video | (filters.document & filters.create(lambda _, __, m: m.document and m.document.file_name.endswith((".mkv", ".mp4")))))
)
async def handle_video(client, message):
    user_id = message.from_user.id
    file_name = message.video.file_name if message.video else message.document.file_name
    file_size = message.video.file_size if message.video else message.document.file_size

    logging.info(f"Receiving video: {file_name} ({file_size / (1024*1024):.2f} MB) from {user_id}")

    async def progress_log(current, total):
        percent = (current / total) * 100
        logging.info(f"Downloading: {current / (1024*1024):.2f}/{total / (1024*1024):.2f} MB ({percent:.2f}%) for user {user_id}")

    video_file = await message.download(progress=progress_log)

    if video_file.endswith(".mp4"):
        new_video_file = video_file.replace(".mp4", ".mkv")
        ffmpeg_cmd = ["ffmpeg", "-i", video_file, "-c", "copy", new_video_file]
        subprocess.run(ffmpeg_cmd, check=True)
        os.remove(video_file)
        video_file = new_video_file

    logging.info(f"Download complete: {video_file}")

    user_data[user_id] = {"video": video_file, "step": "video"}
    await message.reply("Video received! Now send the subtitle file (.ass or .srt).")


# Subtitle Upload Handler
@Bot.on_message(
    filters.user(OWNER_ID) &
    filters.document & filters.create(lambda _, __, m: m.document and m.document.file_name.endswith((".ass", ".srt")))
)
async def handle_subtitle(client, message):
    user_id = message.from_user.id
    subtitle_file = await message.download()

    logging.info(f"Subtitle downloaded: {subtitle_file}")

    # Convert SRT to ASS if needed
    if subtitle_file.endswith(".srt"):
        ass_file = subtitle_file.replace(".srt", ".ass")
        ffmpeg_cmd = ["ffmpeg", "-i", subtitle_file, ass_file]
        subprocess.run(ffmpeg_cmd, check=True)
        os.remove(subtitle_file)  # Remove original SRT file
        subtitle_file = ass_file  # Update to converted file

    # Modify the .ass file
    with open(subtitle_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    modified_lines = []
    for line in lines:
        if line.startswith("Style: Default"):
            line = line.replace("Arial", "Oath-Bold").replace(",16,", ",20,")
        if line.startswith("Dialogue:"):
            parts = line.split(",", 9)  # Ensure the dialogue part is modified
            parts[9] = f"{{\pos(193,265)}}{parts[9]}"
            line = ",".join(parts)
        modified_lines.append(line)

    with open(subtitle_file, "w", encoding="utf-8") as f:
        f.writelines(modified_lines)

    logging.info(f"Modified subtitle file: {subtitle_file}")

    # Send the modified file to the user for review
    await message.reply_document(
        document=subtitle_file,
        caption="Here is the modified subtitle file. Now, please send a new subtitle file."
    )


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
        await message.reply("New name and caption received! Now processing the final video.")
        create_task(merge_subtitles_task(client, message, user_id))
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
        "-metadata:s:s:0", "title=DonghuaWillow",
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
            progress=upload_progress
        )

    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to merge subtitles: {e}")
        await message.reply(f"Error: {e}")

    finally:
        os.remove(video)
        os.remove(subtitle)
        if os.path.exists(output_file):
            os.remove(output_file)
        user_data.pop(user_id, None)
