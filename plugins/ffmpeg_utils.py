import os
import subprocess
import logging
from datetime import datetime
from .video_handler import user_data, logger
from .cleanup import cleanup
from config import DB_CHANNEL, MAIN_CHANNEL
from .link_generation import generate_link
from .channel_post import post_to_main_channel
from .utils import humanbytes

async def merge_subtitles_task(client, message, user_id):
    data = user_data[user_id]
    video = data["video"]
    subtitle = data["subtitle"]
    new_name = data["new_name"]
    caption = data["caption"]
    channel_msg = data.get("channel_msg")  # Get channel message from user_data
    output_file = f"{new_name}.mkv"

    font = 'Assist/Font/OathBold.otf'
    thumbnail = 'Assist/Images/thumbnail.jpg'

    try:
        # Initialize status messages
        status_msg = await message.reply("🔄 Processing video...")
        
        # Update channel msg for processing
        if channel_msg:
            await channel_msg.edit(
                f"🤖 **Bot Processing New File**\n\n"
                f"**File:** `{new_name}`\n"
                f"**Status:** Removing existing subtitles..."
            )

        logger.info(f"Removing existing subtitles from video for user {user_id}")
        remove_subs_cmd = [
            "ffmpeg", "-i", video,
            "-map", "0:v", "-map", "0:a?",
            "-c", "copy", "-y", "removed_subtitles.mkv"
        ]
        subprocess.run(remove_subs_cmd, check=True)

        # Update status for merging
        await status_msg.edit("🔄 Merging subtitles...")
        if channel_msg:
            await channel_msg.edit(
                f"🤖 **Bot Processing New File**\n\n"
                f"**File:** `{new_name}`\n"
                f"**Status:** Merging subtitles and fonts..."
            )

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

        # Update status for upload
        await status_msg.edit("📤 Starting upload...")
        if channel_msg:
            await channel_msg.edit(
                f"🤖 **Bot Processing New File**\n\n"
                f"**File:** `{new_name}`\n"
                f"**Status:** Starting upload..."
            )

        start_time = datetime.now()
        
        # Upload progress callback
        async def progress_callback(current, total):
            try:
                now = datetime.now()
                diff = (now - start_time).seconds
                speed = current / diff if diff > 0 else 0
                percentage = current * 100 / total

                # Create progress bar
                bar_length = 10
                filled_length = int(percentage / 100 * bar_length)
                bar = '■' * filled_length + '□' * (bar_length - filled_length)

                # Update channel message with progress
                if channel_msg:
                    await channel_msg.edit(
                        f"🤖 **Bot Processing New File**\n\n"
                        f"**File:** `{new_name}`\n"
                        f"**Status:** Uploading...\n\n"
                        f"```{bar}``` {percentage:.1f}%\n"
                        f"⚡️ **Speed:** {humanbytes(speed)}/s\n"
                        f"📊 **Progress:** {humanbytes(current)} / {humanbytes(total)}"
                    )
                    
                # Update status message in PM
                await status_msg.edit(
                    f"📤 **Uploading Video**\n\n"
                    f"```{bar}``` {percentage:.1f}%\n"
                    f"⚡️ **Speed:** {humanbytes(speed)}/s\n"
                    f"📊 **Size:** {humanbytes(current)} / {humanbytes(total)}"
                )
            except Exception as e:
                logger.error(f"Progress update failed: {str(e)}")

        # Send file with progress
        sent_message = await message.reply_document(
            document=output_file,
            caption=caption,
            thumb=thumbnail,
            progress=progress_callback
        )

        try:
            # Save to DB_CHANNEL and generate link
            db_msg = await sent_message.copy(chat_id=DB_CHANNEL)
            logger.info(f"File saved to DB_CHANNEL: {output_file}")
            
            link, reply_markup = await generate_link(client, db_msg)
            if link:
                await message.reply_text(
                    f"<b>🔗 Shareable Link:</b>\n\n{link}",
                    reply_markup=reply_markup
                )
                
                # Delete channel progress message and post to main channel
                if channel_msg:
                    await channel_msg.delete()
                await post_to_main_channel(client, new_name, link)
                
        except Exception as e:
            logger.error(f"Failed to save to DB_CHANNEL or generate link: {e}")

        await status_msg.edit("✅ Process Complete!")

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to merge subtitles: {e}")
        await status_msg.edit(f"❌ Error: {e}")
        if channel_msg:
            await channel_msg.delete()
    finally:
        if os.path.exists("removed_subtitles.mkv"):
            os.remove("removed_subtitles.mkv")
        cleanup(user_id)