import subprocess
import logging
from .video_handler import user_data, logger
from .cleanup import cleanup

async def extract_subtitles(client, message, user_id):
    """
    Extract subtitles from video file - No progress bar needed
    """
    data = user_data[user_id]
    video_file = data["video"]
    output_subtitle = video_file.rsplit('.', 1)[0] + ".srt"
    output_ass = video_file.rsplit('.', 1)[0] + ".ass"

    status_msg = await message.reply("Extracting subtitles...")
    try:
        # Extract SRT
        subprocess.run(
            ["ffmpeg", "-i", video_file, "-map", "0:s:0", output_subtitle],
            check=True
        )
        
        # Convert to ASS
        subprocess.run(
            ["ffmpeg", "-i", output_subtitle, output_ass],
            check=True
        )
        
        # Send both files
        await message.reply_document(
            document=output_subtitle,
            caption="📄 Extracted SRT Subtitle"
        )
        await message.reply_document(
            document=output_ass,
            caption="📄 Converted ASS Subtitle"
        )
        
        await status_msg.edit("✅ Subtitles extracted successfully!")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to extract subtitles: {e}")
        await status_msg.edit(f"❌ Error: {e}")
    finally:
        cleanup(user_id)