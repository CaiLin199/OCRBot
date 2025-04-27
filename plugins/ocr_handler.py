from bot import Bot
from pyrogram import filters
import os
import cv2
import pytesseract
import tempfile
import asyncio
from concurrent.futures import ThreadPoolExecutor
from config import LOGGER
import numpy as np
from pathlib import Path

# Initialize logger
logger = LOGGER(__name__)

# Constants
MAX_WORKERS = 4
FRAME_BATCH = 30

# OCR Configuration - Simplified for better text detection
OCR_CONFIG = '--psm 6 --oem 1 -l chi_sim+eng'
os.environ['TESSDATA_PREFIX'] = '/usr/share/tesseract-ocr/4.00/tessdata'

def format_time(seconds):
    """Convert seconds to SRT timestamp format"""
    hrs = seconds // 3600
    mins = (seconds % 3600) // 60
    secs = seconds % 60
    ms = int((seconds % 1) * 1000)
    return f"{int(hrs):02d}:{int(mins):02d}:{int(secs):02d},{ms:03d}"

async def extract_frames(video_path, output_dir):
    """Extract frames using basic settings"""
    try:
        logger.info(f"Starting frame extraction from: {video_path}")
        
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vf', 'fps=2',  # Extract 2 frames per second
            '-vsync', '0',
            '-frame_pts', '1',
            os.path.join(output_dir, 'frame_%d.jpg')
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.communicate()
        frames = [f for f in os.listdir(output_dir) if f.endswith('.jpg')]
        logger.info(f"Extracted {len(frames)} frames")
        return len(frames)

    except Exception as e:
        logger.error(f"Frame extraction error: {str(e)}")
        raise

def process_frame_batch(frames):
    """Process multiple frames efficiently"""
    results = []
    
    for frame_path in frames:
        try:
            frame_num = int(frame_path.split('_')[-1].split('.')[0])
            
            # Read image directly
            image = cv2.imread(frame_path)
            if image is None:
                logger.warning(f"Could not read frame: {frame_path}")
                continue

            # Simple grayscale conversion
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # OCR with relaxed confidence
            ocr_data = pytesseract.image_to_data(
                gray,
                config=OCR_CONFIG,
                output_type=pytesseract.Output.DICT
            )

            # Extract text with lower confidence threshold
            text_parts = []
            for i, conf in enumerate(ocr_data['conf']):
                if conf > 20:  # Lower confidence threshold
                    text = ocr_data['text'][i].strip()
                    if text:
                        text_parts.append(text)

            if text_parts:
                text = ' '.join(text_parts)
                logger.info(f"Frame {frame_num}: Found text: {text[:50]}...")
                results.append((frame_num / 2, text))  # Divide by 2 due to 2 FPS
            
        except Exception as e:
            logger.error(f"Frame processing error: {str(e)}")
        finally:
            try:
                os.remove(frame_path)
            except:
                pass
    
    return results

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
            
            # Create frames directory
            frames_dir = os.path.join(temp_dir, 'frames')
            os.makedirs(frames_dir)
            
            # Extract frames
            await status_msg.edit_text("📥 Extracting frames...")
            total_frames = await extract_frames(video_path, frames_dir)
            
            # Process frames
            await status_msg.edit_text("🔍 Processing frames...")
            all_frames = sorted([os.path.join(frames_dir, f) for f in os.listdir(frames_dir)])
            
            all_results = []
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                for i in range(0, len(all_frames), FRAME_BATCH):
                    batch = all_frames[i:i + FRAME_BATCH]
                    results = executor.submit(process_frame_batch, batch).result()
                    all_results.extend(results)
                    
                    if i % (FRAME_BATCH * 2) == 0:
                        await status_msg.edit_text(
                            f"🔄 Progress: {min(i + FRAME_BATCH, total_frames)}/{total_frames} frames"
                        )
            
            # Generate SRT regardless of results count
            srt_path = os.path.join(temp_dir, 'subtitles.srt')
            with open(srt_path, 'w', encoding='utf-8') as f:
                for i, (time, text) in enumerate(sorted(all_results), 1):
                    f.write(f"{i}\n")
                    f.write(f"{format_time(time)} --> {format_time(time + 0.5)}\n")
                    f.write(f"{text}\n\n")
            
            await message.reply_document(
                document=srt_path,
                caption=f"📝 Extracted {len(all_results)} subtitles from {total_frames} frames"
            )
            
            await status_msg.delete()
            logger.info("Video processing completed")
            
    except Exception as e:
        error_msg = f"Processing error: {str(e)}"
        logger.error(error_msg)
        await message.reply_text(error_msg)