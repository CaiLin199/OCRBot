import os
import asyncio
import logging
import subprocess
from pyrogram import filters, Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from queue import Queue
from tqdm.asyncio import tqdm
from io import BytesIO
import ffmpeg
import psutil
from bot import Bot
from config import OWNER_IDS, LOG_FILE_NAME

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - [%(message)s]')
logger = logging.getLogger(__name__)

# Task queue for FFmpeg operations
task_queue = Queue()

# Temporary storage for user data
user_data = {}

# Resource monitoring function
def log_resources(prefix=""):
    ram = psutil.virtual_memory().percent
    storage = psutil.disk_usage("/").used / (1024 ** 3)  # GB
    cpu = psutil.cpu_percent(interval=None)
    return f"{prefix}RAM: {ram:.1f}% | Storage: {storage:.2f}GB | CPU: {cpu:.1f}%"

# Log file handler
@Bot.on_message(filters.user(OWNER_ID) & filters.command("logs"))
async def get_log_file(client, message):
    try:
        await message.reply_document(document=LOG_FILE_NAME, caption="Log file by SubMerger")
        logger.info(log_resources("Sent log file: "))
    except Exception as e:
        logger.error(f"Failed to send log file: {e}")
        await message.reply(f"Error: {e}")

@Bot.on_message(filters.user(OWNER_ID) & filters.command("final"))
async def start_conversion(client, message):
    await message.reply("Send a subtitle file (.srt or .vtt) for conversion.")

@Bot.on_message(filters.user(OWNER_ID) & filters.command("cleanup"))
async def clear_storage(client, message):
    user_id = message.from_user.id
    await cleanup(user_id)
    await message.reply("Storage cleared.")
    logger.info(log_resources(f"Cleared storage for user {user_id}: "))

# Subtitle conversion handler
@Bot.on_message(filters.user(OWNER_ID) & filters.document & filters.regex(r"\.(srt|vtt)$"))
async def handle_subtitle_conversion(client, message):
    user_id = message.from_user.id
    status_msg = await message.reply("Converting subtitle...")
    try:
        # Download subtitle with tqdm
        subtitle_file = await message.download(
            file_name=f"sub_{user_id}.tmp",
            progress=download_progress
        )
        logger.info(log_resources(f"Subtitle downloaded ({subtitle_file}): "))

        # Convert to ASS in memory
        ass_content = await convert_to_ass(subtitle_file)
        ass_file = f"sub_{user_id}.ass"
        
        # Modify ASS in memory
        modified_ass = modify_ass_content(ass_content)
        with open(ass_file, "w", encoding="utf-8") as f:
            f.write(modified_ass)

        # Send modified subtitle
        await status_msg.edit_text("Uploading subtitle...")
        await client.send_document(
            chat_id=message.chat.id,
            document=ass_file,
            caption="Converted subtitle file."
        )
        logger.info(log_resources(f"Uploaded subtitle ({ass_file}): "))
    except Exception as e:
        logger.error(f"Subtitle conversion failed: {e}")
        await status_msg.edit_text(f"Error: {e}")
    finally:
        for f in [subtitle_file, ass_file]:
            if f and os.path.exists(f):
                os.remove(f)

@Bot.on_message(filters.user(OWNER_ID) & filters.command("merge"))
async def start(client, message):
    await message.reply("Send a video file (MKV or MP4, 400-600 MB).")

# Video upload handler
@Bot.on_message(
    filters.user(OWNER_ID) &
    (filters.video | filters.document & filters.regex(r"\.(mp4|mkv)$"))
)
async def handle_video(client, message):
    user_id = message.from_user.id
    file_name = message.video.file_name if message.video else message.document.file_name
    file_size = message.video.file_size if message.video else message.document.file_size
    if file_size > 650_000_000:  # Cap at ~650 MB
        await message.reply("Video too large, please send under 650 MB.")
        return

    logger.info(log_resources(f"Receiving video ({file_name}, {file_size / (1024**2):.2f}MB): "))
    try:
        status_msg = await message.reply("Downloading video...")
        video_file = await message.download(
            file_name=f"vid_{user_id}.tmp",
            progress=download_progress
        )
        logger.info(log_resources(f"Download complete ({video_file}): "))

        user_data[user_id] = {"video": video_file, "step": "video"}
        
        buttons = [
            [InlineKeyboardButton("Merge", callback_data=f"merge_{user_id}")],
            [InlineKeyboardButton("Extract Sub", callback_data=f"extract_{user_id}")],
            [InlineKeyboardButton("Generate Screenshot", callback_data=f"screenshot_{user_id}")]
        ]
        await status_msg.edit_text("Choose an action:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Video download failed: {e}")
        await status_msg.edit_text(f"Error: {e}")

# Button click handler
@Bot.on_callback_query(filters.regex(r"(merge|extract|screenshot)_(\d+)"))
async def handle_button_click(client, callback_query):
    action, user_id = callback_query.matches[0].groups()
    user_id = int(user_id)
    
    if action == "merge":
        await callback_query.message.edit_text("Send the subtitle file (.ass).")
    elif action == "extract":
        task_queue.put((extract_subtitles, (client, callback_query.message, user_id)))
    elif action == "screenshot":
        task_queue.put((generate_screenshot, (client, callback_query.message, user_id)))
    
    await callback_query.answer()

# Subtitle upload for merging
@Bot.on_message(filters.user(OWNER_ID) & filters.document & filters.regex(r"\.ass$"))
async def handle_subtitle(client, message):
    user_id = message.from_user.id
    try:
        status_msg = await message.reply("Downloading subtitle...")
        subtitle_file = await message.download(
            file_name=f"sub_{user_id}.ass",
            progress=download_progress
        )
        logger.info(log_resources(f"Subtitle downloaded ({subtitle_file}): "))

        user_data[user_id]["subtitle"] = subtitle_file
        user_data[user_id]["step"] = "subtitle"
        await status_msg.edit_text("Send the output file name (without extension).")
    except Exception as e:
        logger.error(f"Subtitle upload failed: {e}")
        await status_msg.edit_text(f"Error: {e}")

# Handle filename
@Bot.on_message(filters.user(OWNER_ID) & filters.text)
async def handle_name_or_caption(client, message):
    user_id = message.from_user.id
    if user_id in user_data and user_data[user_id].get("step") == "subtitle":
        new_name = message.text.strip()
        user_data[user_id]["new_name"] = new_name
        user_data[user_id]["caption"] = new_name
        user_data[user_id]["step"] = "name"
        
        status_msg = await message.reply("Processing video...")
        task_queue.put((merge_subtitles_task, (client, status_msg, user_id)))
    else:
        await message.reply("Please start by sending a video.")

# Async download progress with tqdm in MB
async def download_progress(current, total, *args):
    if not hasattr(download_progress, "bar") or download_progress.bar.total != total:
        download_progress.bar = tqdm(total=total // (1024**2), unit="MB", desc="Downloading")
    download_progress.bar.update((current // (1024**2)) - download_progress.bar.n)
    download_progress.bar.set_postfix_str(log_resources())
    if current >= total:
        download_progress.bar.close()

# Convert subtitle to ASS in memory
async def convert_to_ass(subtitle_file):
    try:
        stream = ffmpeg.input(subtitle_file)
        stream = ffmpeg.output(stream, "-", format="ass", loglevel="error")
        out, _ = await asyncio.to_thread(ffmpeg.run, stream, capture_stdout=True)
        return out.decode("utf-8")
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg ASS conversion failed: {e}")
        raise

# Modify ASS content in memory
def modify_ass_content(ass_content):
    lines = ass_content.splitlines()
    modified_lines = []
    for line in lines:
        if line.startswith("Style: Default"):
            line = line.replace("Arial", "Oath-Bold").replace(",16,", ",20,")
        if line.startswith("Dialogue:"):
            parts = line.split(",", 9)
            if len(parts) > 9:
                parts[9] = f"{{\\pos(193,265)}}{parts[9]}"
            line = ",".join(parts)
        modified_lines.append(line)
    return "\n".join(modified_lines)

# Merge subtitles with progress bar
async def merge_subtitles_task(client, message, user_id):
    data = user_data[user_id]
    video, subtitle, new_name, caption = data["video"], data["subtitle"], data["new_name"], data["caption"]
    output_file = f"out_{user_id}.mkv"
    font = 'Assist/Font/OathBold.otf'
    thumbnail = 'Assist/Images/thumbnail.jpg'

    try:
        # Single FFmpeg command to strip and merge subtitles
        cmd = [
            "ffmpeg", "-i", video, "-i", subtitle,
            "-attach", font, "-metadata:s:t:0", "mimetype=application/x-font-otf",
            "-map", "0:v", "-map", "0:a?", "-map", "1",
            "-metadata:s:s:0", "title=HeavenlySubs",
            "-metadata:s:s:0", "language=eng", "-disposition:s:s:0", "default",
            "-c", "copy", "-y", output_file
        ]
        
        # Run FFmpeg with tqdm
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        total_size = os.path.getsize(video)  # Estimate output size
        bar = tqdm(total=total_size // (1024**2), unit="MB", desc=f"Processing {user_id}")
        
        async def update_bar():
            while True:
                if os.path.exists(output_file):
                    size = os.path.getsize(output_file)
                    bar.update((size // (1024**2)) - bar.n)
                    bar.set_postfix_str(log_resources())
                await asyncio.sleep(0.5)
                if process.returncode is not None:
                    bar.close()
                    break
        
        asyncio.create_task(update_bar())
        await process.wait()
        
        if process.returncode != 0:
            _, stderr = await process.communicate()
            raise subprocess.CalledProcessError(process.returncode, cmd, stderr=stderr.decode())

        # Upload with progress
        async def upload_progress(current, total):
            if not hasattr(upload_progress, "bar") or upload_progress.bar.total != total:
                upload_progress.bar = tqdm(total=total // (1024**2), unit="MB", desc="Uploading")
            upload_progress.bar.update((current // (1024**2)) - upload_progress.bar.n)
            upload_progress.bar.set_postfix_str(log_resources())
            if current >= total:
                upload_progress.bar.close()

        await message.edit_text("Uploading video...")
        await client.send_document(
            chat_id=message.chat.id,
            document=output_file,
            caption=caption,
            thumb=thumbnail,
            progress=upload_progress
        )
        logger.info(log_resources(f"Uploaded merged video ({output_file}): "))
    except Exception as e:
        logger.error(f"Merge failed: {e}")
        await message.edit_text(f"Error: {e}")
    finally:
        await cleanup(user_id)
        if os.path.exists(output_file):
            os.remove(output_file)

# Extract subtitles
async def extract_subtitles(client, message, user_id):
    video_file = user_data[user_id]["video"]
    output_srt = f"sub_{user_id}.srt"
    output_ass = f"sub_{user_id}.ass"
    
    try:
        # Extract SRT
        cmd_srt = ["ffmpeg", "-i", video_file, "-map", "0:s:0", "-y", output_srt]
        process = await asyncio.create_subprocess_exec(*cmd_srt)
        await process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd_srt)

        # Convert to ASS with tqdm
        cmd_ass = ["ffmpeg", "-i", output_srt, "-y", output_ass]
        process = await asyncio.create_subprocess_exec(
            *cmd_ass, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        total_size = os.path.getsize(output_srt) * 2  # Estimate
        bar = tqdm(total=total_size // (1024**2), unit="MB", desc=f"Converting sub {user_id}")
        
        async def update_bar():
            while True:
                if os.path.exists(output_ass):
                    size = os.path.getsize(output_ass)
                    bar.update((size // (1024**2)) - bar.n)
                    bar.set_postfix_str(log_resources())
                await asyncio.sleep(0.5)
                if process.returncode is not None:
                    bar.close()
                    break
        
        asyncio.create_task(update_bar())
        await process.wait()
        
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd_ass)

        await message.edit_text("Uploading subtitles...")
        await client.send_document(chat_id=message.chat.id, document=output_srt, caption="Extracted SRT subtitle.")
        await client.send_document(chat_id=message.chat.id, document=output_ass, caption="Converted ASS subtitle.")
        logger.info(log_resources("Uploaded subtitles: "))
    except Exception as e:
        logger.error(f"Extract failed: {e}")
        await message.edit_text(f"Error: {e}")
    finally:
        for f in [output_srt, output_ass]:
            if os.path.exists(f):
                os.remove(f)

# Generate screenshot
async def generate_screenshot(client, message, user_id):
    video_file = user_data[user_id]["video"]
    screenshot_path = f"shot_{user_id}.png"
    
    try:
        cmd = ["ffmpeg", "-ss", "00:00:05", "-i", video_file, "-frames:v", "1", "-q:v", "2", "-y", screenshot_path]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        total_size = 1_000_000  # Estimate 1 MB
        bar = tqdm(total=total_size // (1024**2), unit="MB", desc=f"Screenshot {user_id}")
        
        async def update_bar():
            while True:
                if os.path.exists(screenshot_path):
                    size = os.path.getsize(screenshot_path)
                    bar.update((size // (1024**2)) - bar.n)
                    bar.set_postfix_str(log_resources())
                await asyncio.sleep(0.5)
                if process.returncode is not None:
                    bar.close()
                    break
        
        asyncio.create_task(update_bar())
        await process.wait()
        
        if process.returncode != 0:
            _, stderr = await process.communicate()
            raise subprocess.CalledProcessError(process.returncode, cmd, stderr=stderr.decode())

        await message.edit_text("Uploading screenshot...")
        await client.send_photo(
            chat_id=message.chat.id,
            photo=screenshot_path,
            caption="Screenshot."
        )
        logger.info(log_resources(f"Uploaded screenshot ({screenshot_path}): "))
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        await message.edit_text(f"Error: {e}")
    finally:
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)

# Cleanup function
async def cleanup(user_id):
    if user_id in user_data:
        for key in ["video", "subtitle"]:
            if key in user_data[user_id] and os.path.exists(user_data[user_id][key]):
                os.remove(user_data[user_id][key])
        user_data.pop(user_id, None)
        logger.info(log_resources(f"Cleaned up for user {user_id}: "))

# Task queue worker
async def queue_worker():
    while True:
        if not task_queue.empty():
            task, args = task_queue.get()
            try:
                await task(*args)
            except Exception as e:
                logger.error(f"Task failed: {e}")
            task_queue.task_done()
        await asyncio.sleep(0.1)  # Prevent CPU hogging

# Start queue worker
asyncio.create_task(queue_worker())
