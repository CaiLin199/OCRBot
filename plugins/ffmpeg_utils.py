import os
import subprocess
import logging
from datetime import datetime
from .video_handler import user_data, logger
from .cleanup import cleanup
from .progress_handler import (
    StatusMessages,
    create_status_messages,
    create_progress_callback,
    update_status_text,
    delete_channel_status
)
from config import DB_CHANNEL, MAIN_CHANNEL
from .link_generation import generate_link
from .channel_post import post_to_main_channel

async def merge_subtitles_task(client, message, user_id):
    """
    Merge subtitles with video file
    Show progress only for download and upload operations
    """
    data = user_data[user_id]
    video = data["video"]
    subtitle = data["subtitle"]
    new_name = data["new_name"]
    caption = data["caption"]
    output_file = f"{new_name}.mkv"
    font = 'Assist/Font/OathBold.otf'
    thumbnail = 'Assist/Images/thumbnail.jpg'
    status_messages = None

    try:
        # Initialize status messages
        status_messages = await create_status_messages(client, message, MAIN_CHANNEL)
        if not status_messages:
            return await message.reply("Failed to initialize status messages.")

        # Download video with progress if it's a message
        if hasattr(video, 'file_id'):
            start_time = datetime.now()
            download_callback = create_progress_callback(
                status_messages,
                start_time,
                "Downloading Video"
            )
            
            video_path = await client.download_media(
                message=video,
                file_name="downloaded_video.mp4",  # Temporary file name
                progress=download_callback
            )
            video = video_path if video_path else video

        # Process video (no progress bar needed)
        logger.info(f"Processing video for user {user_id}")
        await update_status_text(status_messages, "Processing Video...")
        
        # Remove existing subtitles
        remove_subs_cmd = [
            "ffmpeg", "-i", video,
            "-map", "0:v", "-map", "0:a?",
            "-c", "copy", "-y", "removed_subtitles.mkv"
        ]
        subprocess.run(remove_subs_cmd, check=True)

        # Merge subtitles
        logger.info(f"Merging subtitles for user {user_id}")
        await update_status_text(status_messages, "Merging Subtitles...")
        
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

        # Upload with progress bar
        logger.info(f"Starting upload for user {user_id}")
        start_time = datetime.now()
        upload_callback = create_progress_callback(
            status_messages,
            start_time,
            "Uploading Video"
        )
        
        sent_message = await message.reply_document(
            document=output_file,
            caption=caption,
            thumb=thumbnail,
            progress=upload_callback
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
                # Post to main channel
                await post_to_main_channel(client, new_name, link)
                
                # Delete progress message and show completion
                await delete_channel_status(status_messages.channel)
                await status_messages.pm.edit_text(
                    f"✅ Process Complete!\n"
                    f"⌚ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
                )
                
        except Exception as e:
            logger.error(f"Failed to save to DB_CHANNEL or generate link: {e}")
            raise

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg process failed: {e}")
        if status_messages:
            error_text = (
                f"❌ Error in video processing!\n"
                f"⌚ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                f"▫️ Error: {str(e)}"
            )
            await update_status_text(status_messages, error_text)
        raise
        
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        if status_messages:
            error_text = (
                f"❌ An unexpected error occurred!\n"
                f"⌚ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                f"▫️ Error: {str(e)}"
            )
            await update_status_text(status_messages, error_text)
        raise
        
    finally:
        # Cleanup temporary files
        for file in ["removed_subtitles.mkv", "downloaded_video.mp4"]:
            if os.path.exists(file):
                try:
                    os.remove(file)
                except Exception as e:
                    logger.error(f"Failed to remove temporary file {file}: {e}")
        cleanup(user_id)

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