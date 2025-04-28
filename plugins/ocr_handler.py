from bot import Bot
from pyrogram import filters
import os
import cv2
import pytesseract
import tempfile
import asyncio
import json
from config import LOGGER

# Initialize logger
logger = LOGGER(__name__)

# OCR Configuration
OCR_CONFIG = '--psm 6 --oem 1 -l chi_sim'
os.environ['TESSDATA_PREFIX'] = '/usr/share/tesseract-ocr/4.00/tessdata'

def format_time(seconds):
    """Convert seconds to SRT timestamp format"""
    hrs = seconds // 3600
    mins = (seconds % 3600) // 60
    secs = seconds % 60
    ms = int((seconds % 1) * 1000)
    return f"{int(hrs):02d}:{int(mins):02d}:{int(secs):02d},{ms:03d}"

async def get_video_duration(video_path):
    """Get video duration using FFprobe"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries',
            'format=duration',
            '-of', 'json',
            video_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, _ = await process.communicate()
        data = json.loads(stdout)
        return float(data['format']['duration'])
    except Exception as e:
        logger.error(f"Error getting video duration: {e}")
        return 0

async def extract_and_process_frames(video_path, srt_path, progress_msg):
    """Extract and process frames one by one"""
    try:
        duration = await get_video_duration(video_path)
        current_time = 0
        subtitles = []
        frame_count = 0
        
        while current_time < duration:
            # Extract single frame
            frame_path = f'/tmp/frame_{int(current_time)}.jpg'
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
            
            # Update progress every 5 seconds
            if frame_count % 10 == 0:
                progress = (current_time / duration) * 100
                try:
                    await progress_msg.edit_text(
                        f"🔄 Processing: {progress:.1f}%\n"
                        f"⏱ Time: {format_time(current_time)}/{format_time(duration)}\n"
                        f"📝 Subtitles found: {len(subtitles)}"
                    )
                except:
                    pass
            
            # Process frame if exists
            if os.path.exists(frame_path):
                try:
                    # Read and process frame
                    image = cv2.imread(frame_path)
                    if image is not None:
                        # Convert to grayscale
                        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                        
                        # Get text
                        text = pytesseract.image_to_string(gray, config=OCR_CONFIG).strip()
                        
                        # Save if text found
                        if text:
                            subtitles.append((current_time, text))
                            logger.info(f"Found text at {current_time}s: {text[:30]}...")
                except Exception as e:
                    logger.error(f"Error processing frame: {e}")
                finally:
                    # Clean up frame
                    try:
                        os.remove(frame_path)
                    except:
                        pass
            
            frame_count += 1
            current_time += 0.5  # Move forward by 0.5 seconds
        
        # Write SRT file
        with open(srt_path, 'w', encoding='utf-8') as f:
            for i, (time, text) in enumerate(subtitles, 1):
                f.write(f"{i}\n")
                f.write(f"{format_time(time)} --> {format_time(time + 0.5)}\n")
                f.write(f"{text}\n\n")
        
        return len(subtitles)
    
    except Exception as e:
        logger.error(f"Processing error: {str(e)}")
        raise

@Bot.on_message(filters.video | filters.document)
async def process_video(client, message):
    try:
        logger.info("Starting video processing")
        status_msg = await message.reply_text("🎥 Processing video...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download video
            video_path = os.path.join(temp_dir, 'video.mp4')
            await message.download(video_path)
            logger.info("Video downloaded successfully")
            
            # Process video
            srt_path = os.path.join(temp_dir, 'subtitles.srt')
            subtitle_count = await extract_and_process_frames(video_path, srt_path, status_msg)
            
            if subtitle_count > 0:
                await message.reply_document(
                    document=srt_path,
                    caption=f"📝 Extracted {subtitle_count} subtitles"
                )
            else:
                await message.reply_text("No subtitles were found in the video.")
            
            await status_msg.delete()
            logger.info("Video processing completed")
            
    except Exception as e:
        error_msg = f"Processing error: {str(e)}"
        logger.error(error_msg)
        await message.reply_text(f"❌ {error_msg}")