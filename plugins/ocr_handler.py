from bot import Bot
from pyrogram import filters
import os
import cv2
import pytesseract
import tempfile
import asyncio
from config import LOGGER

# Initialize logger
logger = LOGGER(__name__)

# OCR Configuration - Only Chinese since no English text
OCR_CONFIG = '--psm 6 --oem 1 -l chi_sim'
os.environ['TESSDATA_PREFIX'] = '/usr/share/tesseract-ocr/4.00/tessdata'

def format_time(seconds):
    """Convert seconds to SRT timestamp format"""
    hrs = seconds // 3600
    mins = (seconds % 3600) // 60
    secs = seconds % 60
    ms = int((seconds % 1) * 1000)
    return f"{int(hrs):02d}:{int(mins):02d}:{int(secs):02d},{ms:03d}"

async def extract_and_process_frames(video_path, srt_path):
    """Extract frames and process them one by one"""
    try:
        # Get video FPS and duration
        probe_cmd = [
            'ffmpeg',
            '-i', video_path,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams'
        ]
        
        process = await asyncio.create_subprocess_exec(
            *probe_cmd,
            stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        video_info = eval(stdout.decode())
        duration = float(video_info['format']['duration'])
        
        # Process video frame by frame
        subs = []
        current_time = 0
        
        while current_time < duration:
            # Extract single frame
            frame_path = f'/tmp/frame_{current_time}.jpg'
            cmd = [
                'ffmpeg',
                '-ss', str(current_time),
                '-i', video_path,
                '-vframes', '1',
                '-y',
                frame_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            
            # Process frame if exists
            if os.path.exists(frame_path):
                # Read frame and detect text
                image = cv2.imread(frame_path)
                if image is not None:
                    text = pytesseract.image_to_string(image, config=OCR_CONFIG)
                    if text.strip():
                        subs.append((current_time, text.strip()))
                        logger.info(f"Found text at {current_time}s: {text.strip()[:30]}...")
                
                # Clean up frame
                os.remove(frame_path)
            
            current_time += 0.5  # Move forward by 0.5 seconds
            
        # Write SRT file
        with open(srt_path, 'w', encoding='utf-8') as f:
            for i, (time, text) in enumerate(subs, 1):
                f.write(f"{i}\n")
                f.write(f"{format_time(time)} --> {format_time(time + 0.5)}\n")
                f.write(f"{text}\n\n")
        
        return len(subs)
        
    except Exception as e:
        logger.error(f"Processing error: {str(e)}")
        raise

@Bot.on_message(filters.video | filters.document)
async def process_video(client, message):
    try:
        logger.info("Starting video processing")
        status_msg = await message.reply_text("🎥 Processing video...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # 1. Download video
            video_path = os.path.join(temp_dir, 'video.mp4')
            await message.download(video_path)
            logger.info("Video downloaded successfully")
            
            # 2-6. Extract frames, process and save subtitles
            srt_path = os.path.join(temp_dir, 'subtitles.srt')
            subtitle_count = await extract_and_process_frames(video_path, srt_path)
            
            # Send result
            await message.reply_document(
                document=srt_path,
                caption=f"📝 Extracted {subtitle_count} subtitles"
            )
            
            await status_msg.delete()
            logger.info("Video processing completed")
            
    except Exception as e:
        error_msg = f"Processing error: {str(e)}"
        logger.error(error_msg)
        await message.reply_text(error_msg)