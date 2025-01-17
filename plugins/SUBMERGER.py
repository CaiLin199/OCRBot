import os
import subprocess
from bot import Bot
from pyrogram import Client, filters
from pyrogram.types import Message
from config import OWNER_ID, LOGGER


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
        return await message.reply_text("⚠️ Reply to an image to set it as a thumbnail.")

    # Save the thumbnail
    thumbnail_path = os.path.join(UPLOAD_DIR, "thumbnail.jpg")
    await message.reply_to_message.download(file_name=thumbnail_path)
    await message.reply_text("✅ Thumbnail set successfully!")


@Bot.on_message(filters.command("marge") & filters.private & filters.user(OWNER_ID))
async def process_video_or_document(client, message: Message):
    """Process the video or document with the given subtitle and font."""
    LOGGER.info("Send the video or document file to process.")
    await message.reply_text("📥 Please send the video or document file to be processed.")
    
    # Start listening for video or document file
    file_message = await client.listen(message.chat.id, filters.video | filters.document)

    # Check if it's a video or document and process accordingly
    if file_message.video:
        file_type = "video"
        file_path = os.path.join(UPLOAD_DIR, f"{file_message.video.file_id}.mkv")
        await message.reply_text(f"Downloading video: {file_message.video.file_name}...")
    elif file_message.document:
        file_type = "document"
        file_path = os.path.join(UPLOAD_DIR, f"{file_message.document.file_id}.pdf")
        await message.reply_text(f"Downloading document: {file_message.document.file_name}...")
    else:
        await message.reply_text("⚠️ Unsupported file type. Please send a video or document.")
        return

    try:
        # Download the file and log progress
        file_download = await file_message.download(file_name=file_path, progress=lambda current, total: log_progress(current, total, message))
        LOGGER.info(f"📥 File downloaded: {file_path}")

        # Wait for subtitle file
        LOGGER.info("Now send the subtitle file.")
        subtitle_message = await client.listen(message.chat.id, filters.document)
        subtitle_path = os.path.join(UPLOAD_DIR, subtitle_message.document.file_name)
        await subtitle_message.download(file_name=subtitle_path)
        LOGGER.info(f"📥 Subtitle downloaded: {subtitle_path}")

        # Wait for font file
        LOGGER.info("Finally, send the font file.")
        font_message = await client.listen(message.chat.id, filters.document)
        font_path = os.path.join(UPLOAD_DIR, font_message.document.file_name)
        await font_message.download(file_name=font_path)
        LOGGER.info(f"📥 Font downloaded: {font_path}")

        # Prepare the ffmpeg command for video processing if it's a video file
        if file_type == "video":
            output_path = os.path.join(UPLOAD_DIR, f"output_{file_message.video.file_id}.mkv")
            ffmpeg_command = [
                "ffmpeg",
                "-i", file_path,
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
        else:
            # Add a command to handle documents (assuming it's a PDF or similar document)
            output_path = os.path.join(UPLOAD_DIR, f"output_{file_message.document.file_id}.pdf")
            ffmpeg_command = [
                "ffmpeg",
                "-i", file_path,
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

        # Run ffmpeg and capture stdout/stderr
        process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

        LOGGER.info("Processing started...")

        for line in process.stdout:
            LOGGER.info(f"ffmpeg stdout: {line.strip()}")
            if "frame=" in line or "size=" in line:
                await message.reply_text(f"Processing: {line.strip()}")

        # Capture and log errors from stderr
        stderr_output, _ = process.communicate()
        if stderr_output:
            LOGGER.error(f"ffmpeg stderr: {stderr_output}")
            await message.reply_text(f"❌ Processing failed: {stderr_output}")
        else:
            process.wait()

        if process.returncode == 0:
            caption = "🎥 Here's your processed file!"
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
            LOGGER.info("✅ Processing complete!")
        else:
            LOGGER.error(f"❌ Processing failed with return code {process.returncode}.")

    except Exception as e:
        LOGGER.error(f"Error during processing: {str(e)}")
        await message.reply_text(f"❌ Error during processing: {str(e)}")

    # Cleanup
    if os.path.exists(file_path):
        os.remove(file_path)
    if os.path.exists(subtitle_path):
        os.remove(subtitle_path)
    if os.path.exists(font_path):
        os.remove(font_path)
    if os.path.exists(output_path):
        os.remove(output_path)
    if thumbnail_path and os.path.exists(thumbnail_path):
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


def log_progress(current, total, message):
    """Logs download progress and sends updates to the user."""
    percent = (current / total) * 100
    LOGGER.info(f"Download progress: {percent:.2f}%")
    message.edit_text(f"📥 Downloading: {percent:.2f}% completed.")
