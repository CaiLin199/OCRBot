import os
import subprocess
import logging
from .video_handler import user_data, logger
from .cleanup import cleanup

async def generate_screenshot(client, message, user_id):
    """
    Generate screenshot from video - No progress bar needed
    """
    data = user_data[user_id]
    video_file = data["video"]
    screenshot_path = video_file.rsplit('.', 1)[0] + "_screenshot.png"
    
    status_msg = await message.reply("Generating screenshot...")
    try:
        subprocess.run([
            "ffmpeg", "-ss", "00:03:05",
            "-i", video_file,
            "-frames:v", "1",
            "-q:v", "2",
            screenshot_path
        ], check=True)
        
        await message.reply_photo(
            photo=screenshot_path,
            caption="🖼️ Generated Screenshot"
        )
        await status_msg.edit("✅ Screenshot generated!")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to generate screenshot: {e}")
        await status_msg.edit(f"❌ Error: {e}")
    finally:
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)
        cleanup(user_id)