import os
import asyncio
import logging
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot import Bot
from config import OWNER_IDS
from .progress_handler import progress_bar
from datetime import datetime
from .shared_data import user_data, is_auto_mode
from .subtitle_encode import process_subtitle
from .filename import convert_filename
from .ffmpeg_utils import merge_subtitles_task

# Configure logging
logger = logging.getLogger(__name__)

async def extract_subtitle(video_path):
    """Extract subtitle from video file to ASS format"""
    try:
        output_path = video_path.rsplit('.', 1)[0] + ".ass"
        cmd = [
            "ffmpeg", "-i", video_path,
            "-map", "0:s:0",  # Extract first subtitle stream
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.communicate()
        
        if os.path.exists(output_path):
            logger.info(f"Subtitle extracted: {output_path}")
            return output_path
        return None
    except Exception as e:
        logger.error(f"Subtitle extraction failed: {e}")
        return None

@Bot.on_message(
    filters.user(OWNER_IDS) &
    (filters.video | (filters.document & filters.create(lambda _, __, m: m.document and (m.document.file_name.endswith((".mp4", ".mkv"))))))
)
async def handle_video(client, message):
    user_id = message.from_user.id
    file_name = message.video.file_name if message.video else message.document.file_name

    try:
        # Common initial steps for both modes
        status_msg = await message.reply("📥 Downloading video...")
        start_time = datetime.now()

        async def progress_log(current, total):
            try:
                await progress_bar(
                    current, total, 
                    status_msg, 
                    start_time,
                    "Downloading Video",
                    message.from_user.username or f"User_{user_id}"
                )
            except Exception as e:
                logger.error(f"Progress update failed: {e}")

        # Download video with progress
        video_file = await message.download(file_name=file_name, progress=progress_log)
        logger.info(f"Download complete: {video_file}")

        if user_id not in user_data:
            user_data[user_id] = {}
        
        user_data[user_id]["video"] = video_file

        if is_auto_mode():
            # Auto Mode Processing
            await status_msg.edit("🤖 Auto Mode: Extracting subtitle...")
            subtitle_file = await extract_subtitle(video_file)
            
            if subtitle_file:
                # Process subtitle
                await status_msg.edit("✏️ Processing subtitle...")
                success, result = process_subtitle(subtitle_file)
                
                if success:
                    # Generate new filename
                    new_name = convert_filename(file_name)
                    user_data[user_id]["subtitle"] = result
                    user_data[user_id]["new_name"] = new_name
                    
                    await status_msg.edit("🔄 Merging video with subtitle...")
                    await merge_subtitles_task(client, message, user_id)
                else:
                    await status_msg.edit(f"❌ Error processing subtitle: {result}")
            else:
                await status_msg.edit("❌ No subtitle found in video!")
        else:
            # Manual Mode - Show options
            user_data[user_id]["step"] = "video"
            buttons = [
                [InlineKeyboardButton("Merge", callback_data=f"merge_{user_id}")],
                [InlineKeyboardButton("Extract Sub", callback_data=f"extract_{user_id}")],
                [InlineKeyboardButton("Generate Screenshot", callback_data=f"screenshot_{user_id}")]
            ]
            await status_msg.edit(
                "👤 Manual Mode\nChoose an action:", 
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            
    except Exception as e:
        logger.error(f"Video processing failed: {e}")
        await message.reply(f"❌ Error: {str(e)}")