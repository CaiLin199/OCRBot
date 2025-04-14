import os
import asyncio
import logging
from datetime import datetime
from .video_handler import user_data
from .cleanup import cleanup
from .progress_handler import StatusMessages, create_progress_callback, update_status
from config import DB_CHANNEL
from .link_generation import generate_link
from .channel_post import post_to_main_channel

logger = logging.getLogger(__name__)

async def merge_subtitles_task(client, message, user_id: str) -> None:
    """Merge subtitles into video"""
    data = user_data.get(user_id, {})
    if not data:
        await message.reply("❌ Please start over")
        return

    video = data.get("video")
    subtitle = data.get("subtitle")
    new_name = data.get("new_name")
    caption = data.get("caption")
    
    if not all([video, subtitle, new_name]):
        await message.reply("❌ Missing data, please try again")
        return

    output_file = f"{new_name}.mkv"
    font_path = 'Assist/Font/OathBold.otf'
    thumbnail_path = 'Assist/Images/thumbnail.jpg'
    temp_files = []
    status_msg = None

    try:
        status_msg = await message.reply("🎬 Starting...")
        messages = StatusMessages(status_msg, None)

        # Download video if needed
        video_path = video
        if hasattr(video, 'file_id'):
            video_path = await client.download_media(
                message=video,
                progress=create_progress_callback(messages, "Downloading")
            )
            temp_files.append(video_path)

        # Remove existing subtitles
        await update_status(messages, "🔄 Processing...")
        temp_no_subs = "temp_no_subs.mkv"
        temp_files.append(temp_no_subs)
        
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-i", video_path,
            "-map", "0:v", "-map", "0:a?",
            "-c", "copy",
            temp_no_subs,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()

        # Merge subtitles
        await update_status(messages, "🔄 Adding subtitles...")
        process = await asyncio.create_subprocess_exec(
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
            output_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()

        # Upload
        await update_status(messages, "📤 Uploading...")
        sent_message = await message.reply_document(
            document=output_file,
            caption=caption,
            thumb=thumbnail_path,
            progress=create_progress_callback(messages, "Uploading")
        )

        # Save to DB and generate link
        if DB_CHANNEL:
            db_msg = await sent_message.copy(chat_id=DB_CHANNEL)
            link, reply_markup = await generate_link(client, db_msg)
            
            if link:
                await message.reply_text(
                    f"<b>🔗 Here's your link:</b>\n\n{link}",
                    reply_markup=reply_markup
                )
                await post_to_main_channel(client, new_name, link)
                await update_status(messages, "✅ Done!")

    except Exception as e:
        if status_msg:
            await update_status(messages, f"❌ Error: {str(e)}")
    
    finally:
        # Cleanup
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
        cleanup(user_id)