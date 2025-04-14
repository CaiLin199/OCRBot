import os
import subprocess
import logging
from datetime import datetime
from .video_handler import user_data, logger
from .progress_handler import progress_bar

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