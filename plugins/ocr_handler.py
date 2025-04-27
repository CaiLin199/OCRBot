"""
OCR handler with pre-download skip prompt and optimized frame processing
"""

from bot import Bot
from pyrogram import filters
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

# Initialize logger
logger = LOGGER(__name__)

# Constants
BATCH_SIZE = 5
MIN_TEXT_LENGTH = 3
TEXT_SIMILARITY_THRESHOLD = 0.8

document_filter = lambda _, __, msg: bool(msg.document and msg.document.mime_type and 
                                        msg.document.mime_type.startswith('video/'))
video_filter = lambda _, __, msg: bool(msg.video)

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
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
    
    return "".join(parts)

async def get_video_duration(file_size):
    """Estimate video duration based on file size"""
    # Rough estimation: assume 2MB per minute for typical video
    estimated_minutes = file_size / (2 * 1024 * 1024)
    return int(estimated_minutes * 60)

async def extract_frames_efficiently(video_path, output_dir, start_time=0, status_msg=None):
    """Extract frames with hardware acceleration and optimized parameters"""
    try:
        # Check for GPU availability
        gpu_available = False
        try:
            gpu_test = subprocess.run(['nvidia-smi'], capture_output=True)
            gpu_available = gpu_test.returncode == 0
        except:
            pass

        # Base FFmpeg command
        ffmpeg_cmd = [
            'ffmpeg',
            '-ss', str(start_time),  # Start time offset
            '-i', video_path,
            '-vf', 'fps=1,crop=iw:ih/4:0:3*ih/4',  # Extract bottom quarter
            '-frame_pts', '1',
            '-vsync', '0',  # Disable video sync
            '-copyts',      # Copy timestamps
            '-start_number', '0'  # Start frame numbering from 0
        ]

        # Add hardware acceleration if available
        if gpu_available:
            ffmpeg_cmd[1:1] = ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda']

        # Add output path
        ffmpeg_cmd.append(os.path.join(output_dir, 'frame_%d.jpg'))

        # Run FFmpeg
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Monitor progress
        while process.poll() is None:
            if status_msg:
                await status_msg.edit(
                    f"📥 Extracting frames using {'GPU' if gpu_available else 'CPU'}\n"
                    f"⏳ Starting from: {format_time(start_time)}"
                )
            await asyncio.sleep(2)

        if process.returncode != 0:
            stderr = process.stderr.read().decode()
            raise Exception(f"FFmpeg error: {stderr}")

        return True

    except Exception as e:
        logger.error(f"Frame extraction error: {str(e)}")
        raise

@Bot.on_message(filters.create(document_filter) | filters.create(video_filter))
async def process_video(client, message):
    try:
        # Get video size and estimate duration
        file_size = message.document.file_size if message.document else message.video.file_size
        estimated_duration = await get_video_duration(file_size)
        
        # First status message before asking for skip time
        status_msg = await message.reply_text(
            f"🎥 Video detected (Size: {file_size/1024/1024:.1f}MB)\n"
            f"Estimated duration: {format_time(estimated_duration)}\n\n"
            "📝 Enter skip time in format:\n"
            "• `2m` (2 minutes)\n"
            "• `1h30m` (1 hour 30 minutes)\n"
            "• `90s` (90 seconds)\n"
            "• `0` or `skip` to process from start\n\n"
            "⏳ Waiting for your input... (30 seconds)"
        )

        try:
            # Wait for user response
            response = await client.wait_for_message(
                filters.chat(message.chat.id) & 
                filters.user(message.from_user.id) & 
                filters.text,
                timeout=30
            )

            start_time = parse_time_input(response.text)
            
            # Delete prompt and response
            await status_msg.delete()
            await response.delete()
            
            # New status message for download
            status_msg = await message.reply_text("📥 Starting download...")

        except asyncio.TimeoutError:
            start_time = 0
            await status_msg.edit("No input received. Processing from start...")
            await asyncio.sleep(2)

        with tempfile.TemporaryDirectory() as temp_dir:
            # Download file
            video_path = os.path.join(temp_dir, 'video.mp4')
            await message.download(video_path)

            if not os.path.exists(video_path):
                return await status_msg.edit("❌ Failed to download video.")

            # Extract frames
            frames_dir = os.path.join(temp_dir, 'frames')
            os.makedirs(frames_dir, exist_ok=True)

            await status_msg.edit(
                f"🎥 Extracting frames...\n"
                f"⏭ Starting from: {format_time(start_time)}"
            )

            try:
                await extract_frames_efficiently(
                    video_path, 
                    frames_dir, 
                    start_time,
                    status_msg
                )
            except Exception as e:
                return await status_msg.edit(f"❌ Failed to extract frames: {str(e)}")

            # Process frames with optimized batch processing
            frames = sorted([f for f in os.listdir(frames_dir) if f.endswith('.jpg')])
            total_frames = len(frames)
            subtitles = []
            processed = 0

            await status_msg.edit("🔍 Processing frames...")

            with ThreadPoolExecutor(max_workers=4) as executor:
                for i in range(0, total_frames, BATCH_SIZE):
                    batch = frames[i:i + BATCH_SIZE]
                    batch_paths = [os.path.join(frames_dir, f) for f in batch]
                    
                    # Process batch
                    futures = []
                    for frame_path in batch_paths:
                        futures.append(executor.submit(process_frame, frame_path))
                    
                    # Get results and clean up immediately
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
                        finally:
                            # Clean up processed frame
                            try:
                                os.remove(batch_paths[j])
                            except:
                                pass

                    processed += len(batch)
                    if processed % 30 == 0:
                        await status_msg.edit(
                            f"🔍 Processing: {processed}/{total_frames} frames\n"
                            f"📝 Found {len(subtitles)} subtitles"
                        )

            # Generate and upload SRT file
            if not subtitles:
                return await status_msg.edit("❌ No subtitles found in video.")

            srt_path = os.path.join(temp_dir, 'subtitles.srt')
            with open(srt_path, 'w', encoding='utf-8') as f:
                for i, sub in enumerate(subtitles, 1):
                    f.write(f"{i}\n")
                    f.write(f"{format_time(sub['start_time'])} --> {format_time(sub['end_time'])}\n")
                    f.write(f"{sub['text']}\n\n")

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
        if status_msg:
            await status_msg.edit(error_msg)

def process_frame(frame_path):
    """Process a single frame with optimized OCR"""
    try:
        # Read image
        image = cv2.imread(frame_path)
        if image is None:
            return None

        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Apply adaptive threshold
        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )

        # OCR the image
        text = pytesseract.image_to_string(
            thresh,
            lang='eng',
            config='--psm 6 --oem 3'
        ).strip()

        return text if len(text) >= MIN_TEXT_LENGTH else None

    except Exception as e:
        logger.error(f"Frame processing error: {str(e)}")
        return None