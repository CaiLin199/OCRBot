import os
import subprocess
import logging
from datetime import datetime
from .video_handler import user_data, logger
from .progress_handler import progress_bar

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