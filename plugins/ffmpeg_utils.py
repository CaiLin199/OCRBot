import os
import subprocess
import logging
from datetime import datetime
from .video_handler import user_data, logger
from .cleanup import cleanup
from .shared_data import progress_bar
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
    
    try:
        # Initialize status message
        status_msg = await message.reply("Starting process...")
        
        # Download video with progress if it's a message
        if hasattr(video, 'file_id'):
            video_path = await client.download_media(
                message=video,
                progress=lambda c, t: progress_bar(c, t, status_msg, "Downloading")
            )
            video = video_path if video_path else video

        # Process video (no progress bar needed)
        await status_msg.edit("Processing Video...")
        remove_subs_cmd = [
            "ffmpeg", "-i", video,
            "-map", "0:v", "-map", "0:a?",
            "-c", "copy", "-y", "removed_subtitles.mkv"
        ]
        subprocess.run(remove_subs_cmd, check=True)

        # Merge subtitles
        await status_msg.edit("Merging Subtitles...")
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

        # Upload with progress
        await status_msg.edit("Starting Upload...")
        sent_message = await message.reply_document(
            document=output_file,
            caption=caption,
            thumb=thumbnail,
            progress=lambda c, t: progress_bar(c, t, status_msg, "Uploading")
        )

        # Save to DB_CHANNEL and generate link
        try:
            db_msg = await sent_message.copy(chat_id=DB_CHANNEL)
            link, reply_markup = await generate_link(client, db_msg)
            
            if link:
                await message.reply_text(
                    f"<b>🔗 Shareable Link:</b>\n\n{link}",
                    reply_markup=reply_markup
                )
                await post_to_main_channel(client, new_name, link)
                await status_msg.edit("✅ Process Complete!")
                
        except Exception as e:
            logger.error(f"Failed to save to DB_CHANNEL or generate link: {e}")
            raise

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg process failed: {e}")
        if status_msg:
            await status_msg.edit(f"❌ Error in video processing: {str(e)}")
        
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        if status_msg:
            await status_msg.edit(f"❌ Error: {str(e)}")
        
    finally:
        # Cleanup temporary files
        for file in ["removed_subtitles.mkv", video if isinstance(video, str) else None]:
            if file and os.path.exists(file):
                try:
                    os.remove(file)
                except Exception as e:
                    logger.error(f"Failed to remove temporary file {file}: {e}")
        cleanup(user_id)