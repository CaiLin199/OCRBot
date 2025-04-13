import os
import subprocess
import logging
from asyncio import create_task
from .video_handler import user_data
from .cleanup import cleanup

async def merge_subtitles_task(client, message, user_id):
    data = user_data[user_id]
    video = data["video"]
    subtitle = data["subtitle"]
    new_name = data["new_name"]
    caption = data["caption"]
    output_file = f"{new_name}.mkv"

    font = 'Assist/Font/OathBold.otf'
    thumbnail = 'Assist/Images/thumbnail.jpg'

    try:
        # Remove existing subtitles
        remove_subs_cmd = [
            "ffmpeg", "-i", video,
            "-map", "0:v", "-map", "0:a?",
            "-c", "copy", "-y", "removed_subtitles.mkv"
        ]
        subprocess.run(remove_subs_cmd, check=True)

        # Add new subtitle
        ffmpeg_cmd = [
            "ffmpeg", "-i", "removed_subtitles.mkv",
            "-i", subtitle,
            "-attach", font, "-metadata:s:t:0", "mimetype=application/x-font-otf",
            "-map", "0", "-map", "1",
            "-metadata:s:s:0", "title=HeavenlySubs",
            "-metadata:s:s:0", "language=eng", "-disposition:s:s:0", "default",
            "-c", "copy", output_file
        ]
        subprocess.run(ffmpeg_cmd, check=True)

        async def upload_progress(current, total):
            percent = (current / total) * 100
            logger.info(f"Uploading: {current / (1024*1024):.2f}/{total / (1024*1024):.2f} MB ({percent:.2f}%) for user {user_id}")

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
        if os.path.exists("removed_subtitles.mkv"):
            os.remove("removed_subtitles.mkv")
        cleanup(user_id)

async def extract_subtitles(client, message, user_id):
    data = user_data[user_id]
    video_file = data["video"]
    output_subtitle = video_file.rsplit('.', 1)[0] + ".srt"
    output_ass = video_file.rsplit('.', 1)[0] + ".ass"

    try:
        subprocess.run(["ffmpeg", "-i", video_file, "-map", "0:s:0", output_subtitle], check=True)
        subprocess.run(["ffmpeg", "-i", output_subtitle, output_ass], check=True)

        await message.reply_document(document=output_subtitle, caption="Here is the extracted subtitle file.")
        await message.reply_document(document=output_ass, caption="Here is the converted ASS subtitle file.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to extract subtitles: {e}")
        await message.reply(f"Error: {e}")

async def generate_screenshot(client, message, user_id):
    data = user_data[user_id]
    video_file = data["video"]
    screenshot_path = video_file.rsplit('.', 1)[0] + "_screenshot.png"
    timestamp = "00:00:05"

    try:
        subprocess.run([
            "ffmpeg", "-ss", timestamp, "-i", video_file,
            "-frames:v", "1", "-q:v", "2",
            screenshot_path
        ], check=True)

        await message.reply_photo(photo=screenshot_path, caption="Here is the screenshot.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to generate screenshot: {e}")
        await message.reply(f"Error: {e}")
