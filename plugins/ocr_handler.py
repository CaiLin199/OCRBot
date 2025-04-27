import os
import subprocess
import numpy as np
import pytesseract
import tempfile
from PIL import Image
from config import LOGGER
import time
import cv2
import math
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor
from bot import Bot
from pyrogram import filters

# Initialize logger
logger = LOGGER(__name__)

# Constants
BATCH_SIZE = 5
MIN_TEXT_LENGTH = 3
TEXT_SIMILARITY_THRESHOLD = 0.8

# Store active users' states
active_users = {}

def parse_time_input(time_str):
    """Parse time input in format like '2m', '1h30m', '90s', etc."""
    if not time_str:
        return 0
    
    if time_str.lower() in ['0', 'skip', 'no']:
        return 0
        
    total_seconds = 0
    pairs = re.findall(r'(\d+)([hms])', time_str.lower())
    
    for value, unit in pairs:
        value = int(value)
        if unit == 'h':
            total_seconds += value * 3600
        elif unit == 'm':
            total_seconds += value * 60
        elif unit == 's':
            total_seconds += value
            
    return total_seconds

def format_time(seconds):
    """Format seconds into readable time string"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    elif minutes > 0:
        parts.append(f"{minutes:02d}:{seconds:02d}")
    else:
        parts.append(f"00:{seconds:02d}")
    
    return "".join(parts)

async def get_video_duration(file_size):
    """Estimate video duration based on file size"""
    estimated_minutes = file_size / (2 * 1024 * 1024)
    return int(estimated_minutes * 60)

async def extract_frames_efficiently(video_path, output_dir, start_time=0, status_msg=None):
    """Extract frames with hardware acceleration and optimized parameters"""
    try:
        # Base FFmpeg command with optimized parameters
        ffmpeg_cmd = [
            'ffmpeg',
            '-hide_banner',
            '-loglevel', 'error',
            '-ss', str(start_time),
            '-i', video_path,
            '-vf', 'fps=1,crop=iw:ih/4:0:3*ih/4',
            '-frame_pts', '1',
            '-vsync', '0',
            '-f', 'image2',
            '-pix_fmt', 'yuv420p',
            os.path.join(output_dir, 'frame_%d.jpg')
        ]

        # Try using hardware acceleration
        try:
            gpu_test = subprocess.run(['nvidia-smi'], capture_output=True)
            if gpu_test.returncode == 0:
                ffmpeg_cmd[1:1] = ['-hwaccel', 'cuda']
        except:
            pass  # No GPU available

        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        while process.poll() is None:
            if status_msg:
                try:
                    await status_msg.edit_text(
                        f"📥 Extracting frames...\n"
                        f"⏳ Starting from: {format_time(start_time)}"
                    )
                except:
                    pass
            await asyncio.sleep(2)

        if process.returncode != 0:
            stderr = process.stderr.read().decode()
            raise Exception(f"FFmpeg error: {stderr}")

        return True

    except Exception as e:
        logger.error(f"Frame extraction error: {str(e)}")
        raise

def process_frame(frame_path):
    """Process a single frame with optimized OCR"""
    try:
        # Read image with OpenCV
        image = cv2.imread(frame_path)
        if image is None:
            return None

        # Image preprocessing
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (3,3), 0)
        thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

        # OCR with optimized parameters
        text = pytesseract.image_to_string(
            thresh,
            lang='eng',
            config='--psm 6 --oem 3 -c tessedit_char_whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?-():; "'
        ).strip()

        return text if len(text) >= MIN_TEXT_LENGTH else None

    except Exception as e:
        logger.error(f"Frame processing error: {str(e)}")
        return None
    finally:
        try:
            os.remove(frame_path)
        except:
            pass

@Bot.on_message(filters.command(["start"]))
async def start_command(client, message):
    await message.reply_text(
        "👋 Hello! I can help you extract subtitles from videos.\n"
        "Just send me any video file and I'll guide you through the process!"
    )

@Bot.on_message(filters.video | filters.document)
async def handle_video(client, message):
    try:
        # Check if it's a video
        if not (message.video or (message.document and message.document.mime_type and 
                                message.document.mime_type.startswith('video/'))):
            return
            
        user_id = message.from_user.id
        
        # Get video info
        file_size = message.video.file_size if message.video else message.document.file_size
        estimated_duration = await get_video_duration(file_size)
        
        # Ask for skip time
        status_msg = await message.reply_text(
            f"🎥 Video detected!\n"
            f"💾 Size: {file_size/1024/1024:.1f}MB\n"
            f"⏱ Estimated duration: {format_time(estimated_duration)}\n\n"
            "📝 Enter skip time (or 0 to start from beginning):\n"
            "Examples:\n"
            "• `5m` (5 minutes)\n"
            "• `1h30m` (1 hour 30 minutes)\n"
            "• `90s` (90 seconds)\n"
            "• `0` (start from beginning)\n\n"
            "⏳ Waiting for your input... (30 seconds)"
        )
        
        # Store user state
        active_users[user_id] = {
            'waiting_for_time': True,
            'message_id': message.id,
            'status_msg': status_msg
        }
        
        try:
            # Wait for response
            response = await client.wait_for_message(
                chat_id=message.chat.id,
                filters=filters.user(user_id) & filters.text,
                timeout=30
            )
            
            start_time = parse_time_input(response.text)
            
            # Clean up messages
            await status_msg.edit_text("Processing your video...")
            try:
                await response.delete()
            except:
                pass
                
        except asyncio.TimeoutError:
            start_time = 0
            await status_msg.edit_text("No input received, starting from beginning...")

        # Clear user state
        if user_id in active_users:
            del active_users[user_id]

        # Process video
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download video
            video_path = os.path.join(temp_dir, 'video.mp4')
            await message.download(video_path)

            if not os.path.exists(video_path):
                return await status_msg.edit_text("❌ Failed to download video.")

            # Extract and process frames
            frames_dir = os.path.join(temp_dir, 'frames')
            os.makedirs(frames_dir, exist_ok=True)

            try:
                await extract_frames_efficiently(video_path, frames_dir, start_time, status_msg)
            except Exception as e:
                return await status_msg.edit_text(f"❌ Failed to extract frames: {str(e)}")

            # Process frames
            frames = sorted([f for f in os.listdir(frames_dir) if f.endswith('.jpg')])
            total_frames = len(frames)
            subtitles = []
            processed = 0

            # Process frames in batches
            with ThreadPoolExecutor(max_workers=4) as executor:
                for i in range(0, total_frames, BATCH_SIZE):
                    batch = frames[i:i + BATCH_SIZE]
                    batch_paths = [os.path.join(frames_dir, f) for f in batch]
                    futures = [executor.submit(process_frame, path) for path in batch_paths]

                    for j, future in enumerate(futures):
                        try:
                            text = future.result()
                            if text:
                                frame_time = start_time + i + j
                                subtitles.append({
                                    'start_time': frame_time,
                                    'end_time': frame_time + 1,
                                    'text': text
                                })
                        except Exception as e:
                            logger.error(f"Error processing frame: {str(e)}")

                    processed += len(batch)
                    if processed % 30 == 0:
                        await status_msg.edit_text(
                            f"🔍 Processing: {processed}/{total_frames} frames\n"
                            f"📝 Found {len(subtitles)} subtitles"
                        )

            if not subtitles:
                return await status_msg.edit_text("❌ No subtitles found in video.")

            # Generate SRT file
            srt_path = os.path.join(temp_dir, 'subtitles.srt')
            with open(srt_path, 'w', encoding='utf-8') as f:
                for i, sub in enumerate(subtitles, 1):
                    f.write(f"{i}\n")
                    f.write(f"{format_time(sub['start_time'])} --> {format_time(sub['end_time'])}\n")
                    f.write(f"{sub['text']}\n\n")

            # Send result
            await message.reply_document(
                document=srt_path,
                caption=f"✅ Extracted {len(subtitles)} subtitles\n"
                        f"🎞 Processed {total_frames} frames\n"
                        f"⏭ Started from: {format_time(start_time)}"
            )
            await status_msg.delete()

    except Exception as e:
        error_msg = f'❌ Error: {str(e)}'
        logger.error(error_msg)
        if 'status_msg' in locals():
            await status_msg.edit_text(error_msg)

# Add error handler
@Bot.on_message(filters.all)
async def error_handler(client, message):
    try:
        raise message.stop_propagation()
    except Exception as e:
        logger.error(f"Error in message handler: {str(e)}")