import os
import subprocess
import logging
from datetime import datetime
from .video_handler import user_data, logger
from .cleanup import cleanup
from .progress_handler import progress_bar
from config import DB_CHANNEL, MAIN_CHANNEL
from .link_generation import generate_link
from .channel_post import post_to_main_channel

async def merge_subtitles_task(client, message, user_id):
    data = user_data[user_id]
    video = data["video"]
    subtitle = data["subtitle"]
    new_name = data["new_name"]
    caption = data["caption"]
    output_file = f"{new_name}.mkv"

    font = 'Assist/Font/OathBold.otf'
    thumbnail = 'Assist/Images/thumbnail.jpg'

    status_msg = None
    channel_msg = None
    
    try:
        # Create both messages first
        status_msg = await message.reply("📥 Starting Download Process...")
        channel_msg = await client.send_message(MAIN_CHANNEL, "📥 Starting Download Process...")
        start_time = datetime.now()

        # Separate progress update function for download
        async def download_progress(current, total):
            try:
                progress_text = f"📥 **Downloading Video**\n\n"
                percentage = current * 100 / total
                progress_text += f"**{percentage:.1f}%** of **{humanbytes(total)}**\n"
                progress_text += f"**Speed:** {humanbytes(current//(datetime.now() - start_time).seconds)}/s\n"
                
                # Update both messages with the same progress
                await status_msg.edit(progress_text)
                await channel_msg.edit(progress_text)
            except Exception as e:
                logger.error(f"Download progress update failed: {str(e)}")

        # Handle video download with progress
        if hasattr(video, 'file_id'):
            downloaded_file = await client.download_media(
                message=video,
                progress=download_progress
            )
            video = downloaded_file

        # After download complete, update both messages
        await status_msg.edit("✅ Download Complete\n🔄 Starting Process...")
        await channel_msg.edit("✅ Download Complete\n🔄 Starting Process...")

        # Remove existing subtitles
        await status_msg.edit("🗑 Removing existing subtitles...")
        await channel_msg.edit("🗑 Removing existing subtitles...")
        
        logger.info(f"Removing existing subtitles from video for user {user_id}")
        remove_subs_cmd = [
            "ffmpeg", "-i", video,
            "-map", "0:v", "-map", "0:a?",
            "-c", "copy", "-y", "removed_subtitles.mkv"
        ]
        subprocess.run(remove_subs_cmd, check=True)

        # Merge subtitles
        await status_msg.edit("🔄 Merging subtitles and fonts...")
        await channel_msg.edit("🔄 Merging subtitles and fonts...")
        
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

        # Upload process
        await status_msg.edit("📤 Starting upload...")
        await channel_msg.edit("📤 Starting upload...")
        start_time = datetime.now()

        # Upload progress callback
        async def upload_progress(current, total):
            try:
                progress_text = f"📤 **Uploading Video**\n\n"
                percentage = current * 100 / total
                progress_text += f"**{percentage:.1f}%** of **{humanbytes(total)}**\n"
                progress_text += f"**Speed:** {humanbytes(current//(datetime.now() - start_time).seconds)}/s\n"
                
                # Update both messages with the same progress
                await status_msg.edit(progress_text)
                await channel_msg.edit(progress_text)
            except Exception as e:
                logger.error(f"Upload progress update failed: {str(e)}")

        # Send to user with progress
        sent_message = await message.reply_document(
            document=output_file,
            caption=caption,
            thumb=thumbnail,
            progress=upload_progress
        )

        # Save to DB_CHANNEL
        try:
            db_msg = await sent_message.copy(chat_id=DB_CHANNEL)
            logger.info(f"File saved to DB_CHANNEL: {output_file}")
            
            # Generate and send link
            link, reply_markup = await generate_link(client, db_msg)
            if link:
                share_text = f"<b>🔗 Shareable Link:</b>\n\n{link}"
                await message.reply_text(share_text, reply_markup=reply_markup)
                await channel_msg.edit(share_text, reply_markup=reply_markup)
                
                # Post to main channel
                await post_to_main_channel(client, new_name, link)
                            
        except Exception as e:
            logger.error(f"Failed to save to DB_CHANNEL or generate link: {e}")

        # Final status update
        await status_msg.edit("✅ Process Complete!")
        await channel_msg.edit("✅ Process Complete!")

    except subprocess.CalledProcessError as e:
        error_msg = f"❌ Error: {e}"
        logger.error(f"Failed to merge subtitles: {e}")
        if status_msg and channel_msg:
            await status_msg.edit(error_msg)
            await channel_msg.edit(error_msg)
    finally:
        if os.path.exists("removed_subtitles.mkv"):
            os.remove("removed_subtitles.mkv")
        cleanup(user_id)

def humanbytes(size):
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'