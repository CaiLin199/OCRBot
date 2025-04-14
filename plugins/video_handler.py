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

@Bot.on_message(
    filters.user(OWNER_IDS) &
    (filters.video | (filters.document & filters.create(lambda _, __, m: m.document and (m.document.file_name.endswith((".mp4", ".mkv"))))))
)
async def handle_video(client, message):
    user_id = message.from_user.id
    file_name = message.video.file_name if message.video else message.document.file_name

    try:
        # Create initial status messages
        status_msg = await message.reply("📥 Downloading video...")
        channel_msg = await client.send_message(
            MAIN_CHANNEL,
            f"🤖 **Bot Processing New File**\n\n"
            f"**File:** `{file_name}`\n"
            f"**Status:** Starting Download..."
        )
        start_time = datetime.now()

        async def progress_log(current, total):
            try:
                now = datetime.now()
                diff = (now - start_time).seconds
                speed = current / diff if diff > 0 else 0
                percentage = current * 100 / total
                
                # Progress bar
                bar_length = 10
                filled_length = int(percentage / 100 * bar_length)
                bar = '■' * filled_length + '□' * (bar_length - filled_length)
                
                # Update PM message
                await status_msg.edit(
                    f"📥 **Downloading Video**\n\n"
                    f"```{bar}``` {percentage:.1f}%\n"
                    f"⚡️ **Speed:** {humanbytes(speed)}/s\n"
                    f"📊 **Size:** {humanbytes(current)} / {humanbytes(total)}"
                )
                
                # Update channel message
                await channel_msg.edit(
                    f"🤖 **Bot Processing New File**\n\n"
                    f"**File:** `{file_name}`\n"
                    f"**Status:** Downloading...\n\n"
                    f"```{bar}``` {percentage:.1f}%\n"
                    f"⚡️ **Speed:** {humanbytes(speed)}/s\n"
                    f"📊 **Progress:** {humanbytes(current)} / {humanbytes(total)}"
                )
                
            except Exception as e:
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
            await status_msg.edit("🤖 Auto Mode: Extracting subtitle...")
            await channel_msg.edit(
                f"🤖 **Bot Processing New File**\n\n"
                f"**File:** `{new_name}`\n"
                f"**Status:** Extracting subtitle..."
            )
            
            subtitle_file = await extract_subtitle(video_file)
            
            if subtitle_file:
                # Process subtitle
                await status_msg.edit("✏️ Processing subtitle...")
                await channel_msg.edit(
                    f"🤖 **Bot Processing New File**\n\n"
                    f"**File:** `{new_name}`\n"
                    f"**Status:** Processing subtitle..."
                )
                
                success, result = process_subtitle(subtitle_file)
                
                if success:
                    user_data[user_id]["subtitle"] = result
                    
                    await status_msg.edit("🔄 Merging video with subtitle...")
                    await channel_msg.edit(
                        f"🤖 **Bot Processing New File**\n\n"
                        f"**File:** `{new_name}`\n"
                        f"**Status:** Merging video with subtitle..."
                    )
                    
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