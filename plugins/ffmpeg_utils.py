import os
import subprocess
import logging
from datetime import datetime
from .video_handler import user_data, logger
from .cleanup import cleanup
from .progress_handler import ProgressHandler
from config import DB_CHANNEL
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
    progress = None

    try:
        # Initialize progress handler
        progress = ProgressHandler(client, message)
        await progress.init_messages()

        # Handle video download with progress
        if hasattr(video, 'file_id'):
            downloaded_file = await client.download_media(
                message=video,
                progress=lambda current, total: progress.update_progress(
                    current, total, "📥 Downloading Video"
                )
            )
            video = downloaded_file

        # Update status for subtitle removal
        await progress.update_status("🗑 Removing existing subtitles...")
        
        remove_subs_cmd = [
            "ffmpeg", "-i", video,
            "-map", "0:v", "-map", "0:a?",
            "-c", "copy", "-y", "removed_subtitles.mkv"
        ]
        subprocess.run(remove_subs_cmd, check=True)

        # Update status for merging
        await progress.update_status("🔄 Merging subtitles...")
        
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
        await progress.update_status("📤 Starting upload...")

        # Send to user with progress
        sent_message = await message.reply_document(
            document=output_file,
            caption=caption,
            thumb=thumbnail,
            progress=lambda current, total: progress.update_progress(
                current, total, "📤 Uploading Video"
            )
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
                
                # Clean up channel progress message and post final message
                await progress.finished()
                await post_to_main_channel(client, new_name, link)
                
        except Exception as e:
            logger.error(f"Failed to save to DB_CHANNEL or generate link: {e}")

        await progress.update_status("✅ Process Complete!")

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to merge subtitles: {e}")
        if progress:
            await progress.update_status(f"❌ Error: {e}")
    finally:
        if os.path.exists("removed_subtitles.mkv"):
            os.remove("removed_subtitles.mkv")
        if progress:
            await progress.finished()
        cleanup(user_id)