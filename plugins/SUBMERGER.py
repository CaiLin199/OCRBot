import os
import subprocess
from bot import Bot
from pyrogram import Client, filters
from pyrogram.types import Message
from config import OWNER_ID


# Directory to save files
UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Variable to store the thumbnail path
thumbnail_path = None


@Bot.on_message(filters.command("thumb") & filters.private & filters.user(OWNER_ID))
async def set_thumbnail(client, message: Message):
    """Set a custom thumbnail for the processed file."""
    global thumbnail_path
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply_text("Reply to an image to set it as a thumbnail.")

    # Save the thumbnail
    thumbnail_path = os.path.join(UPLOAD_DIR, "thumbnail.jpg")
    await message.reply_to_message.download(file_name=thumbnail_path)
    await message.reply_text("✅ Thumbnail set successfully!")


@Bot.on_message(filters.command("marge") & filters.private & filters.user(OWNER_ID))
async def process_video(client, message: Message):
    """Process the video with the given subtitle and font."""
    if not message.reply_to_message or not message.reply_to_message.video:
        return await message.reply_text("Reply to a video to process it.")

    # Download the video file
    video = message.reply_to_message.video
    video_path = os.path.join(UPLOAD_DIR, f"{video.file_id}.mkv")
    await message.reply_to_message.download(file_name=video_path)
    await message.reply_text(f"📥 Video downloaded: `{video_path}`")

    # Wait for subtitle file
    await message.reply_text("Now send the subtitle file...")
    subtitle_message = await client.listen(message.chat.id, filters=document)
    subtitle_path = os.path.join(UPLOAD_DIR, subtitle_message.document.file_name)
    await subtitle_message.download(file_name=subtitle_path)
    await message.reply_text(f"📥 Subtitle downloaded: `{subtitle_path}`")

    # Wait for font file
    await message.reply_text("Finally, send the font file...")
    font_message = await client.listen(message.chat.id, filters=document)
    font_path = os.path.join(UPLOAD_DIR, font_message.document.file_name)
    await font_message.download(file_name=font_path)
    await message.reply_text(f"📥 Font downloaded: `{font_path}`")

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

    # Run ffmpeg
    process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    await message.reply_text("Processing started...")

    for line in process.stdout:
        if "frame=" in line or "size=" in line:
            await message.reply_text(f"Processing: {line.strip()}")

    process.wait()

    if process.returncode == 0:
        caption = "🎥 Here's your processed video!"
        if thumbnail_path:
            await client.send_document(
                chat_id=message.chat.id,
                document=output_path,
                thumb=thumbnail_path,
                caption=caption,
            )
        else:
            await client.send_document(
                chat_id=message.chat.id,
                document=output_path,
                caption=caption,
            )
        await message.reply_text("✅ Processing complete!")
    else:
        await message.reply_text("❌ Processing failed.")

    # Cleanup
    os.remove(video_path)
    os.remove(subtitle_path)
    os.remove(font_path)
    os.remove(output_path)
    if thumbnail_path:
        os.remove(thumbnail_path)
        thumbnail_path = None


@Bot.on_message(filters.command("clearthumb") & filters.private & filters.user(OWNER_ID))
async def clear_thumbnail(client, message: Message):
    """Clear the custom thumbnail."""
    global thumbnail_path
    if thumbnail_path and os.path.exists(thumbnail_path):
        os.remove(thumbnail_path)
        thumbnail_path = None
        await message.reply_text("✅ Thumbnail cleared successfully.")
    else:
        await message.reply_text("⚠️ No thumbnail to clear.")
