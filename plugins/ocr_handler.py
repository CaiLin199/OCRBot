"""
Create a Python Telegram bot that processes a video, extracts the bottom 1/4th of the video frames,
and performs OCR on these cropped frames. Generate accurate timestamps for subtitles.
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

# Initialize logger
logger = LOGGER(__name__)

document_filter = lambda _, __, msg: bool(msg.document and msg.document.mime_type and 
                                        msg.document.mime_type.startswith('video/'))
video_filter = lambda _, __, msg: bool(msg.video)

def humanbytes(size):
    if not size:
        return "0B"
    power = 2**10
    n = 0
    Dic_powerN = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'

@Bot.on_message(filters.create(document_filter) | filters.create(video_filter))
async def process_video(client, message):
    try:
        status_msg = await message.reply_text("Starting video processing...")
        start_time = time.time()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download file
            video_path = os.path.join(temp_dir, 'video.mp4')
            await status_msg.edit("📥 Downloading video...")
            
            try:
                # Get file size for logging
                file_size = message.document.file_size if message.document else message.video.file_size
                logger.info(
                    f"Starting download for {message.from_user.first_name} ({message.from_user.id})\n"
                    f"File size: {humanbytes(file_size)}"
                )
                
                await message.download(video_path)
                download_time = time.time() - start_time
                logger.info(
                    f"Video downloaded in {download_time:.1f}s\n"
                    f"Speed: {humanbytes(file_size/download_time)}/s"
                )
            except Exception as e:
                logger.error(f"Download failed: {str(e)}")
                return await status_msg.edit("Failed to download video.")
            
            if not os.path.exists(video_path):
                logger.error("Video download failed: File not found")
                return await status_msg.edit("Failed to download video.")
            
            # Process video and generate subtitles
            await status_msg.edit("🔍 Processing video and extracting subtitles...")
            srt_path = await extract_subtitles(video_path, temp_dir, status_msg)
            
            if srt_path and os.path.exists(srt_path):
                await status_msg.edit("📤 Uploading subtitles...")
                await message.reply_document(
                    document=srt_path,
                    caption="Here are your extracted subtitles!"
                )
                await status_msg.delete()
                total_time = time.time() - start_time
                logger.info(
                    f"✅ Process completed for {message.from_user.first_name} ({message.from_user.id})\n"
                    f"Total time: {total_time:.1f}s"
                )
            else:
                await status_msg.edit("No subtitles were found in the video.")
                logger.warning(f"No subtitles found in video from {message.from_user.first_name}")
                
    except Exception as e:
        error_msg = f'Error processing video: {str(e)}'
        logger.error(f"Error: {error_msg}\nUser: {message.from_user.first_name}")
        await message.reply_text(error_msg)

async def extract_subtitles(video_path, temp_dir, status_msg):
    subtitles = []
    frames_dir = os.path.join(temp_dir, 'frames')
    os.makedirs(frames_dir, exist_ok=True)
    
    # Get video info
    try:
        # Get video duration using ffprobe
        duration_cmd = subprocess.run([
            'ffprobe', 
            '-v', 'error',
            '-show_entries', 
            'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ], capture_output=True, text=True)
        
        duration = float(duration_cmd.stdout.strip() or '0')
        
        # Default to 1 fps for frame extraction
        fps = 1.0
        total_frames = int(duration)
        
        logger.info(
            f"📊 Video Info:\n"
            f"Duration: {duration:.1f}s\n"
            f"Extracting at: {fps} fps\n"
            f"Expected frames: {total_frames}"
        )
        
    except Exception as e:
        logger.error(f"Error getting video duration: {str(e)}")
        return None
    
    try:
        # Extract frames using ffmpeg (1 frame per second)
        extract_start = time.time()
        ffmpeg_cmd = [
            'ffmpeg', '-i', video_path,
            '-vf', 'fps=1,crop=iw:ih/4:0:3*ih/4',  # Extract bottom quarter at 1 fps
            '-frame_pts', '1',
            os.path.join(frames_dir, 'frame_%d.jpg')
        ]
        
        process = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {process.stderr}")
            return None
            
        extract_time = time.time() - extract_start
        logger.info(f"Frames extracted in {extract_time:.1f}s")
        
        # Process extracted frames
        frame_files = sorted([f for f in os.listdir(frames_dir) if f.endswith('.jpg')])
        total_frames = len(frame_files)
        processed_frames = 0
        last_text = ""
        ocr_start = time.time()
        
        for i, frame_file in enumerate(frame_files):
            frame_path = os.path.join(frames_dir, frame_file)
            
            try:
                # Read frame and perform OCR
                image = Image.open(frame_path)
                text = pytesseract.image_to_string(
                    image,
                    lang='eng',
                    config='--psm 6 --oem 3'
                ).strip()
                
                if text and text != last_text:
                    subtitles.append({
                        'start_time': i,
                        'end_time': i + 1,
                        'text': text
                    })
                    last_text = text
                
                processed_frames += 1
                if processed_frames % 10 == 0:  # Log every 10 frames
                    logger.info(
                        f"OCR Progress: {processed_frames}/{total_frames} frames "
                        f"({(processed_frames/total_frames*100):.1f}%)"
                    )
                    
            except Exception as e:
                logger.error(f"Error processing frame {frame_file}: {str(e)}")
            finally:
                # Clean up frame file
                try:
                    os.remove(frame_path)
                except Exception as e:
                    logger.error(f"Error removing frame {frame_file}: {str(e)}")
        
        ocr_time = time.time() - ocr_start
        logger.info(
            f"✅ OCR completed:\n"
            f"Processed {processed_frames} frames in {ocr_time:.1f}s\n"
            f"Found {len(subtitles)} subtitle entries\n"
            f"Speed: {processed_frames/ocr_time:.1f} frames/s"
        )
        
    except Exception as e:
        logger.error(f"Error in frame extraction/OCR: {str(e)}")
        return None
    
    if not subtitles:
        return None
        
    # Generate SRT file
    srt_path = os.path.join(temp_dir, 'subtitles.srt')
    if await generate_srt(subtitles, srt_path):
        return srt_path
    return None

async def generate_srt(subtitles, output_path):
    def format_time(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        milliseconds = 0
        return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, subtitle in enumerate(subtitles, 1):
                f.write(f"{i}\n")
                f.write(f"{format_time(subtitle['start_time'])} --> {format_time(subtitle['end_time'])}\n")
                f.write(f"{subtitle['text']}\n\n")
        
        logger.info(f"Generated SRT file with {len(subtitles)} entries")
        return True
        
    except Exception as e:
        logger.error(f"Error generating SRT file: {str(e)}")
        return False