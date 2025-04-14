import os
import subprocess
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from .video_handler import user_data, logger
from .cleanup import cleanup
from .shared_data import progress_bar, create_progress_callback
from config import DB_CHANNEL, MAIN_CHANNEL
from .link_generation import generate_link
from .channel_post import post_to_main_channel

class FFmpegError(Exception):
    """Custom exception for FFmpeg related errors"""
    pass

async def merge_subtitles_task(client, message, user_id: str) -> None:
    """
    Merge subtitles into video with enhanced error handling and progress tracking
    """
    data: Dict[str, Any] = user_data.get(user_id, {})
    if not data:
        raise ValueError("No user data found")

    video = data.get("video")
    subtitle = data.get("subtitle")
    new_name = data.get("new_name")
    caption = data.get("caption")
    
    if not all([video, subtitle, new_name]):
        raise ValueError("Missing required data (video, subtitle, or name)")

    output_file = f"{new_name}.mkv"
    font_path = 'Assist/Font/OathBold.otf'
    thumbnail_path = 'Assist/Images/thumbnail.jpg'
    temp_files = []
    status_msg = None

    try:
        # Validate input files
        for file_path in [font_path, thumbnail_path]:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Required file not found: {file_path}")

        # Initialize status message
        status_msg = await message.reply("🎬 Initializing process...")
        start_time = datetime.now()

        # Handle video download if it's a message
        video_path = video
        if hasattr(video, 'file_id'):
            progress_callback = await create_progress_callback(status_msg, "Downloading Video")
            video_path = await client.download_media(
                message=video,
                progress=progress_callback
            )
            temp_files.append(video_path)

        # Remove existing subtitles
        await status_msg.edit("🔄 Processing video...")
        temp_no_subs = "temp_no_subs.mkv"
        temp_files.append(temp_no_subs)
        
        remove_subs_cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-map", "0:v", "-map", "0:a?",
            "-c", "copy",
            temp_no_subs
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *remove_subs_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise FFmpegError(f"Failed to remove subtitles: {stderr.decode()}")
        except Exception as e:
            raise FFmpegError(f"Error in subtitle removal: {str(e)}")

        # Merge subtitles
        await status_msg.edit("🔄 Merging subtitles...")
        temp_files.append(output_file)
        
        merge_cmd = [
            "ffmpeg", "-y",
            "-i", temp_no_subs,
            "-i", subtitle,
            "-attach", font_path,
            "-metadata:s:t:0", "mimetype=application/x-font-otf",
            "-map", "0", "-map", "1",
            "-metadata:s:s:0", "title=HeavenlySubs",
            "-metadata:s:s:0", "language=eng",
            "-disposition:s:s:0", "default",
            "-c", "copy",
            output_file
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *merge_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise FFmpegError(f"Failed to merge subtitles: {stderr.decode()}")
        except Exception as e:
            raise FFmpegError(f"Error in subtitle merging: {str(e)}")

        # Upload file
        if not os.path.exists(output_file):
            raise FileNotFoundError("Output file was not created")

        await status_msg.edit("📤 Starting upload...")
        progress_callback = await create_progress_callback(status_msg, "Uploading")
        
        sent_message = await message.reply_document(
            document=output_file,
            caption=caption,
            thumb=thumbnail_path,
            progress=progress_callback
        )

        # Save to DB_CHANNEL and generate link
        try:
            db_msg = await sent_message.copy(chat_id=DB_CHANNEL)
            link, reply_markup = await generate_link(client, db_msg)
            
            if link:
                await message.reply_text(
                    f"<b>🔗 Here's your shareable link:</b>\n\n{link}",
                    reply_markup=reply_markup
                )
                await post_to_main_channel(client, new_name, link)
                await status_msg.edit("✅ Process completed successfully!")
            else:
                raise ValueError("Failed to generate sharing link")

        except Exception as e:
            logger.error(f"Failed to save to DB_CHANNEL or generate link: {e}")
            raise

    except FileNotFoundError as e:
        error_msg = f"❌ File not found: {str(e)}"
        logger.error(error_msg)
        if status_msg:
            await status_msg.edit(error_msg)

    except FFmpegError as e:
        error_msg = f"❌ FFmpeg error: {str(e)}"
        logger.error(error_msg)
        if status_msg:
            await status_msg.edit(error_msg)

    except Exception as e:
        error_msg = f"❌ An unexpected error occurred: {str(e)}"
        logger.error(error_msg)
        if status_msg:
            await status_msg.edit(error_msg)

    finally:
        # Cleanup temporary files
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                logger.error(f"Failed to remove temporary file {temp_file}: {e}")

        # Cleanup user data
        cleanup(user_id)

async def get_video_info(video_path: str) -> Dict[str, Any]:
    """Get video information using FFprobe"""
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise FFmpegError(f"FFprobe failed: {stderr.decode()}")
            
        import json
        return json.loads(stdout.decode())
        
    except Exception as e:
        logger.error(f"Failed to get video info: {e}")
        return {}