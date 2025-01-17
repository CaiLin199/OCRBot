import os
import subprocess
from bot import Bot
from config import OWNER_ID
from pyrogram import Client, filters
from pyrogram.types import Message

# Directory to save files
UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Variable to store the thumbnail path
thumbnail_path = None


@Bot.on_message(filters.command("thumb") & filters.private & filter.user(OWNER_ID))
async def set_thumbnail(client, message: Message):
    """Set a custom thumbnail for the processed file."""
    global thumbnail_path
    if not message.reply_to_message or not message.reply_to_message.photo:
        
        return

    # Save the thumbnail
    thumbnail_path = os.path.join(UPLOAD_DIR, "thumbnail.jpg")
    await message.reply_to_message.download(file_name=thumbnail_path)
    await message.reply_text("Thumbnail set successfully!")


@Bot.on_message(filters.command("marge") & filters.private & filter.user(OWNER_ID))
async def process_video(client, message: Message):
    """Process the video with the given subtitle and font."""
    if not message.reply_to_message or not message.reply_to_message.video:
        
        return

    # Download the video file
    video = message.reply_to_message.video
    video_path = os.path.join(UPLOAD_DIR, f"{video.file_id}.mkv")
    await message.reply_to_message.download(file_name=video_path)
    await message.reply_text(f"Video downloaded: `{video_path}`")

    # Expecting subtitle and font files to be sent in separate messages
    subtitle_message = await app.listen(message.chat.id, filters=document)
    subtitle = subtitle_message.document
    subtitle_path = os.path.join(UPLOAD_DIR, subtitle.file_name)
    await subtitle_message.download(file_name=subtitle_path)
    await message.reply_text(f"Subtitle downloaded: `{subtitle_path}`")

    font_message = await app.listen(message.chat.id, filters=document)
    font = font_message.document
    font_path = os.path.join(UPLOAD_DIR, font.file_name)
    await font_message.download(file_name=font_path)
    await message.reply_text(f"Font downloaded: `{font_path}`")

    # Prepare the ffmpeg command
    output_path = os.path.join(UPLOAD_DIR, f"output_{video.file_id}.mkv")
    ffmpeg_command = [
        "ffmpeg",
        "-i", video_path,
        "-i", subtitle_path,
        "-attach", font_path,
        "-metadata:s:t:0", "mimetype=application/x-font-otf",
        "-map", "0",
        "-map", "1",
        "-metadata:s:s:0", "title=HeavenlySubs",
        "-metadata:s:s:0", "language=eng",
        "-disposition:s:s:0", "default",
        "-c", "copy",
        output_path
    ]

    # Run ffmpeg and capture the output
    process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    await message.reply_text("Processing started...")

    progress_message = await message.reply_text("Progress: 0%")
    try:
        for line in process.stdout:
            # Parse progress from ffmpeg output
            if "frame=" in line or "size=" in line:
                await progress_message.edit_text(f"Processing: {line.strip()}")
        
        process.wait()
    except Exception as e:
        await message.reply_text(f"Error occurred: {e}")
        return

    if process.returncode == 0:
        # Send the processed file back to the user
        caption = ""
        if thumbnail_path:
            await app.send_document(
                chat_id=message.chat.id,
                document=output_path,
                thumb=thumbnail_path,
                caption=caption
            )
        else:
            await app.send_document(chat_id=message.chat.id, document=output_path, caption=caption)

        await message.reply_text("Processing complete!")
    else:
        await message.reply_text("Processing failed.")

    # Cleanup
    os.remove(video_path)
    os.remove(subtitle_path)
    os.remove(font_path)
    os.remove(output_path)
    if thumbnail_path:
        os.remove(thumbnail_path)
        thumbnail_path = None


@Bot.on_message(filters.command("clearthumb") & filters.private & filter.user(OWNER_ID))
async def clear_thumbnail(client, message: Message):
    """Clear the custom thumbnail."""
    global thumbnail_path
    if thumbnail_path and os.path.exists(thumbnail_path):
        os.remove(thumbnail_path)
        thumbnail_path = None
        await message.reply_text("Thumbnail cleared successfully.")
    else:
        await message.reply_text("No thumbnail to clear.")

