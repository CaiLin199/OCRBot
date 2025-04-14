import os
import asyncio
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot import Bot
from config import OWNER_IDS, MAIN_CHANNEL
from datetime import datetime
from .shared_data import user_data, is_auto_mode, logger
from .subtitle_encode import process_subtitle
from .filename import convert_filename
from .ffmpeg_utils import merge_subtitles_task
from .subtitle_utils import extract_subtitles

@Bot.on_message(
    filters.user(OWNER_IDS) &
    (filters.video | (filters.document & filters.create(lambda _, __, m: m.document and (m.document.file_name.endswith((".mp4", ".mkv"))))))
)
async def handle_video(client, message):
    user_id = message.from_user.id
    file_name = message.video.file_name if message.video else message.document.file_name

    try:
        # Create initial status messages
        status_msg = await message.reply("📥 Starting Download...")
        channel_msg = await client.send_message(
            MAIN_CHANNEL,
            "Status: Starting download..."
        )
        start_time = datetime.now()
        last_update_time = datetime.now()
        update_interval = 7  # 7 seconds between updates

        async def progress_log(current, total):
            try:
                nonlocal last_update_time
                now = datetime.now()
                
                # Check if enough time has passed since last update
                if (now - last_update_time).seconds < update_interval:
                    return
                    
                last_update_time = now
                diff = (now - start_time).seconds
                
                # Calculate speed
                speed = current / diff if diff > 0 else 0
                percentage = current * 100 / total
                
                # Calculate ETA
                if speed > 0:
                    eta = (total - current) / speed
                    eta_hours = int(eta // 3600)
                    eta_minutes = int((eta % 3600) // 60)
                    eta_seconds = int(eta % 60)
                else:
                    eta_hours = eta_minutes = eta_seconds = 0
                
                # Calculate elapsed time
                elapsed_minutes = diff // 60
                elapsed_seconds = diff % 60
                
                # Progress bar
                bar_length = 10
                filled_length = int(percentage / 100 * bar_length)
                bar = '[' + '■' * filled_length + '□' * (bar_length - filled_length) + ']'
                
                # Format progress text
                progress_text = (
                    f"Progress: {bar} {percentage:.1f}%\n"
                    f"📥 Downloading: {humanbytes(current)} | {humanbytes(total)}\n"
                    f"⚡️ Speed: {humanbytes(speed)}/s\n"
                    f"⌛ ETA: {eta_hours}h {eta_minutes}m {eta_seconds}s\n"
                    f"⏱️ Time elapsed: {elapsed_minutes}m {elapsed_seconds}s"
                )
                
                # Update both messages
                try:
                    await status_msg.edit(progress_text)
                except Exception as e:
                    if "420 FLOOD_WAIT" not in str(e):
                        logger.error(f"PM progress update failed: {str(e)}")
                
                try:
                    await channel_msg.edit(progress_text)
                except Exception as e:
                    if "420 FLOOD_WAIT" not in str(e):
                        logger.error(f"Channel progress update failed: {str(e)}")
                
            except Exception as e:
                if "420 FLOOD_WAIT" not in str(e):
                    logger.error(f"Progress update failed: {str(e)}")

        # Download video with progress
        video_file = await message.download(file_name=file_name, progress=progress_log)
        logger.info(f"Download complete: {video_file}")

        if user_id not in user_data:
            user_data[user_id] = {}
        
        user_data[user_id].update({
            "video": video_file,
            "channel_msg": channel_msg  # Store channel message for later updates
        })
        
        # Convert filename to new format
        new_name = convert_filename(file_name)
        user_data[user_id].update({
            "new_name": new_name,
            "caption": new_name
        })

        if is_auto_mode():
            # Auto Mode Processing
            await status_msg.edit("🔄 Auto Mode: Extracting subtitle...")
            await channel_msg.edit("Status: Extracting subtitle...")
            
            subtitle_file = await extract_subtitle(video_file)
            
            if subtitle_file:
                # Process subtitle
                await status_msg.edit("✏️ Processing subtitle...")
                await channel_msg.edit("Status: Processing subtitle...")
                
                success, result = process_subtitle(subtitle_file)
                
                if success:
                    user_data[user_id]["subtitle"] = result
                    
                    await status_msg.edit("🔄 Merging video with subtitle...")
                    await channel_msg.edit("Status: Merging video with subtitle...")
                    
                    await merge_subtitles_task(client, message, user_id)
                else:
                    await status_msg.edit(f"❌ Error processing subtitle: {result}")
                    await channel_msg.delete()
            else:
                await status_msg.edit("❌ No subtitle found in video!")
                await channel_msg.delete()
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
            await channel_msg.delete()
            
    except Exception as e:
        logger.error(f"Video processing failed: {e}")
        await message.reply(f"❌ Error: {str(e)}")
        if 'channel_msg' in locals():
            await channel_msg.delete()

def humanbytes(size):
    if not size:
        return "0B"
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{size:.2f}{units[index]}"