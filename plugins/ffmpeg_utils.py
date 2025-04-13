import os
import subprocess
import logging
from datetime import datetime
from .video_handler import user_data, logger
from .cleanup import cleanup
from .progress_handler import progress_bar
from config import DB_CHANNEL

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
        status_msg = await message.reply("Processing video...")
        
        logger.info(f"Removing existing subtitles from video for user {user_id}")
        remove_subs_cmd = [
            "ffmpeg", "-i", video,
            "-map", "0:v", "-map", "0:a?",
            "-c", "copy", "-y", "removed_subtitles.mkv"
        ]
        subprocess.run(remove_subs_cmd, check=True)

        await status_msg.edit("Merging subtitles...")
        logger.info(f"Merging subtitles for user {user_id}: {output_file}")
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

        await status_msg.edit("Starting upload...")
        start_time = datetime.now()
        
        async def upload_progress(current, total):
            try:
                await progress_bar(
                    current,
                    total,
                    status_msg,
                    start_time,
                    "Uploading Video",
                    message.from_user.username or f"User_{user_id}"
                )
            except Exception as e:
                logger.error(f"Progress update failed: {str(e)}")

        # Send to user
        sent_message = await message.reply_document(
            document=output_file,
            caption=caption,
            thumb=thumbnail,
            progress=upload_progress
        )

        # Save copy of the message to DB_CHANNEL
        try:
            await sent_message.copy(chat_id=DB_CHANNEL)
            logger.info(f"File saved to DB_CHANNEL: {output_file}")
        except Exception as e:
            logger.error(f"Failed to save to DB_CHANNEL: {e}")

        await status_msg.edit("✅ Upload Complete!")

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to merge subtitles: {e}")
        await status_msg.edit(f"❌ Error: {e}")
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
        status_msg = await message.reply("Extracting subtitles...")
        logger.info(f"Extracting subtitles from {video_file}")
        
        subprocess.run(["ffmpeg", "-i", video_file, "-map", "0:s:0", output_subtitle], check=True)
        logger.info(f"Subtitles extracted to {output_subtitle}")

        subprocess.run(["ffmpeg", "-i", output_subtitle, output_ass], check=True)
        logger.info(f"Subtitles converted to {output_ass}")

        start_time = datetime.now()

        async def upload_progress(current, total):
            try:
                await progress_bar(
                    current,
                    total,
                    status_msg,
                    start_time,
                    "Uploading Subtitle",
                    message.from_user.username or f"User_{user_id}"
                )
            except Exception as e:
                logger.error(f"Progress update failed: {str(e)}")

        await message.reply_document(
            document=output_subtitle,
            caption="Here is the extracted subtitle file.",
            progress=upload_progress
        )
        
        start_time = datetime.now()  # Reset start time for second upload
        await message.reply_document(
            document=output_ass,
            caption="Here is the converted ASS subtitle file.",
            progress=upload_progress
        )

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to extract subtitles: {e}")
        await status_msg.edit(f"❌ Error: {e}")

async def generate_screenshot(client, message, user_id):
    data = user_data[user_id]
    video_file = data["video"]
    screenshot_path = video_file.rsplit('.', 1)[0] + "_screenshot.png"
    timestamp = "00:03:05"

    try:
        status_msg = await message.reply("Generating screenshot...")
        logger.info(f"Generating screenshot from {video_file} at {timestamp}")
        
        subprocess.run([
            "ffmpeg", "-ss", timestamp, "-i", video_file,
            "-frames:v", "1", "-q:v", "2",
            screenshot_path
        ], check=True)
        logger.info(f"Screenshot saved to {screenshot_path}")

        start_time = datetime.now()

        async def upload_progress(current, total):
            try:
                await progress_bar(
                    current,
                    total,
                    status_msg,
                    start_time,
                    "Uploading Screenshot",
                    message.from_user.username or f"User_{user_id}"
                )
            except Exception as e:
                logger.error(f"Progress update failed: {str(e)}")

        await message.reply_photo(
            photo=screenshot_path,
            caption="Here is the screenshot.",
            progress=upload_progress
        )
        
        await status_msg.edit("✅ Screenshot generated and uploaded!")

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to generate screenshot: {e}")
        await status_msg.edit(f"❌ Error: {e}")