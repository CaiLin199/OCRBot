from bot import Bot
from pyrogram import filters
import os
import cv2
import pytesseract
import tempfile
from PIL import Image
import asyncio
from concurrent.futures import ThreadPoolExecutor
from config import LOGGER
import numpy as np

# Initialize logger
logger = LOGGER(__name__)

# Constants for optimization
MAX_WORKERS = 4
FRAME_BATCH = 30
MIN_TEXT_LENGTH = 3

# OCR Configuration for better Chinese + English detection
OCR_CONFIG = '--psm 6 --oem 1 -l chi_sim+eng --dpi 300'
TESSDATA_DIR = '/usr/share/tesseract-ocr/4.00/tessdata'
os.environ['TESSDATA_PREFIX'] = TESSDATA_DIR

def format_time(seconds):
    """Convert seconds to SRT timestamp format"""
    hrs = seconds // 3600
    mins = (seconds % 3600) // 60
    secs = seconds % 60
    ms = int((seconds % 1) * 1000)
    return f"{int(hrs):02d}:{int(mins):02d}:{int(secs):02d},{ms:03d}"

async def extract_frames(video_path, output_dir):
    """Extract frames using optimized FFmpeg settings"""
    try:
        # FFmpeg command with optimized settings
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vf',
            'fps=1,crop=iw:ih/4:0:3*ih/4,scale=w=trunc(min(iw,1280)/2)*2:h=-2,eq=contrast=1.2:brightness=0.1',
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
        return len([f for f in os.listdir(output_dir) if f.endswith('.jpg')])

    except Exception as e:
        logger.error(f"Frame extraction error: {str(e)}")
        raise

def enhance_image(image):
    """Optimize image for better OCR accuracy"""
    try:
        # Apply CLAHE for better contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(image)
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(enhanced, h=10)
        
        # Adaptive thresholding
        binary = cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2
        )
        
        return binary
    except Exception as e:
        logger.error(f"Image enhancement error: {str(e)}")
        return image

def process_frame_batch(frames):
    """Process multiple frames efficiently"""
    results = []
    
    for frame_path in frames:
        try:
            # Get frame number
            frame_num = int(frame_path.split('_')[-1].split('.')[0])
            
            # Read and process image
            image = cv2.imread(frame_path, cv2.IMREAD_GRAYSCALE)
            if image is None:
                continue

            # Enhance image
            processed = enhance_image(image)
            
            # Perform OCR
            text = pytesseract.image_to_string(
                processed,
                config=OCR_CONFIG
            ).strip()
            
            if text and len(text) >= MIN_TEXT_LENGTH:
                results.append((frame_num, text))
            
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
        status_msg = await message.reply_text("🎥 Processing video...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download video
            video_path = os.path.join(temp_dir, 'video.mp4')
            await message.download(video_path)
            
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
            
            if all_results:
                # Merge similar consecutive subtitles
                merged = []
                current = None
                
                for frame_num, text in sorted(all_results):
                    if not current:
                        current = {'start': frame_num, 'end': frame_num + 1, 'text': text}
                        continue
                    
                    if frame_num - current['end'] <= 2 and text == current['text']:
                        current['end'] = frame_num + 1
                    else:
                        merged.append(current)
                        current = {'start': frame_num, 'end': frame_num + 1, 'text': text}
                
                if current:
                    merged.append(current)
                
                # Generate SRT
                srt_path = os.path.join(temp_dir, 'subtitles.srt')
                with open(srt_path, 'w', encoding='utf-8') as f:
                    for i, sub in enumerate(merged, 1):
                        f.write(f"{i}\n")
                        f.write(f"{format_time(sub['start'])} --> {format_time(sub['end'])}\n")
                        f.write(f"{sub['text']}\n\n")
                
                await message.reply_document(document=srt_path)
            else:
                await message.reply_text("No text found")
            
            await status_msg.delete()
            
    except Exception as e:
        logger.error(str(e))
        await message.reply_text(f"Error: {str(e)}")