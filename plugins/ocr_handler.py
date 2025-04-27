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
import asyncio
from concurrent.futures import ThreadPoolExecutor
import gc

# Initialize logger
logger = LOGGER(__name__)

# Constants
BATCH_SIZE = 10
MIN_TEXT_LENGTH = 3
TEXT_SIMILARITY_THRESHOLD = 0.8
SKIP_TIME = 120  # 2 minutes in seconds
MAX_WORKERS = 4  # Reduced for stability
OCR_CONFIDENCE_THRESHOLD = 40

# OCR Configuration
TESSERACT_CONFIG = '--psm 6 --oem 3 -c tessedit_char_whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?-():; " --dpi 70'

def format_time(seconds):
    """Format seconds into readable time string"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}"

def optimize_image_for_ocr(image):
    """Optimize image for better OCR accuracy"""
    try:
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Create a copy to avoid memory issues
        image = image.copy()

        # 1. Denoise
        denoised = cv2.fastNlMeansDenoising(image)
        
        # 2. Increase contrast using CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        contrasted = clahe.apply(denoised)
        
        # 3. Thresholding
        _, thresh = cv2.threshold(contrasted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 4. Remove small noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        # Ensure proper cleanup
        del denoised, contrasted, thresh
        gc.collect()
        
        return cleaned
    except Exception as e:
        logger.error(f"Image optimization failed: {str(e)}")
        return image

async def extract_frames_efficiently(video_path, output_dir, start_time=SKIP_TIME, status_msg=None):
    """Extract frames with maximum efficiency"""
    try:
        logger.info(f"Starting frame extraction from: {start_time}s")
        
        # Optimize FFmpeg command
        ffmpeg_cmd = [
            'ffmpeg',
            '-hwaccel', 'auto',
            '-ss', str(start_time),
            '-i', video_path,
            '-vf', 'fps=1,crop=iw:ih/4:0:3*ih/4',
            '-frame_pts', '1',
            '-vsync', '0',
            '-f', 'image2',
            '-start_number', '0',
            os.path.join(output_dir, 'frame_%d.jpg')
        ]

        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {stderr.decode()}")
            raise Exception(f"FFmpeg error: {stderr.decode()}")

        frame_count = len([f for f in os.listdir(output_dir) if f.endswith('.jpg')])
        logger.info(f"Extracted {frame_count} frames")
        return frame_count

    except Exception as e:
        logger.error(f"Frame extraction error: {str(e)}")
        raise

def process_frame_batch(frames):
    """Process a batch of frames efficiently"""
    results = []
    
    for frame_path in frames:
        try:
            # Read image
            image = cv2.imread(frame_path, cv2.IMREAD_GRAYSCALE)
            if image is None:
                logger.error(f"Failed to read image: {frame_path}")
                continue

            # Optimize image
            optimized = optimize_image_for_ocr(image)
            
            # Convert to PIL Image
            pil_image = Image.fromarray(optimized)
            
            try:
                # OCR with confidence check
                ocr_data = pytesseract.image_to_data(
                    pil_image,
                    lang='eng',
                    config=TESSERACT_CONFIG,
                    output_type=pytesseract.Output.DICT
                )

                # Filter by confidence and collect text
                text_parts = [
                    ocr_data['text'][i].strip()
                    for i, conf in enumerate(ocr_data['conf'])
                    if float(conf) > OCR_CONFIDENCE_THRESHOLD and ocr_data['text'][i].strip()
                ]

                text = ' '.join(text_parts).strip()
                
                if len(text) >= MIN_TEXT_LENGTH:
                    results.append(text)

            finally:
                # Clean up PIL Image
                pil_image.close()
                del pil_image
                
                # Clean up OpenCV images
                del image
                del optimized
                
                # Force garbage collection
                gc.collect()

        except Exception as e:
            logger.error(f"Frame processing error: {str(e)}")
        finally:
            try:
                os.remove(frame_path)
            except Exception as e:
                logger.error(f"Failed to remove frame: {str(e)}")

    return results

@Bot.on_message(filters.video | filters.document)
async def process_video(client, message):
    try:
        if not (message.video or (message.document and 
                message.document.mime_type and 
                message.document.mime_type.startswith('video/'))):
            await message.reply_text("❌ Please send a video file.")
            return

        status_msg = await message.reply_text(
            "🎥 Processing your video...\n"
            "⏳ This might take a few minutes"
        )
        
        start_time = time.time()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = os.path.join(temp_dir, 'video.mp4')
            await message.download(
                video_path,
                progress=lambda c, t: logger.info(f"Download: {(c/t)*100:.1f}%")
            )

            frames_dir = os.path.join(temp_dir, 'frames')
            os.makedirs(frames_dir, exist_ok=True)

            await status_msg.edit_text("📥 Extracting frames...")
            total_frames = await extract_frames_efficiently(video_path, frames_dir, SKIP_TIME, status_msg)

            if total_frames == 0:
                return await status_msg.edit_text(
                    "❌ Could not extract frames.\n"
                    "The video might be too short or corrupted."
                )

            frames = sorted([f for f in os.listdir(frames_dir) if f.endswith('.jpg')])
            subtitles = []
            processed = 0

            await status_msg.edit_text("🔍 Processing frames...")

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = []
                for i in range(0, len(frames), BATCH_SIZE):
                    batch = frames[i:i + BATCH_SIZE]
                    batch_paths = [os.path.join(frames_dir, f) for f in batch]
                    futures.append(executor.submit(process_frame_batch, batch_paths))

                for i, future in enumerate(futures):
                    try:
                        texts = future.result()
                        frame_base = i * BATCH_SIZE
                        
                        for j, text in enumerate(texts):
                            frame_time = SKIP_TIME + frame_base + j
                            subtitles.append({
                                'start_time': frame_time,
                                'end_time': frame_time + 1,
                                'text': text
                            })
                            
                        processed += BATCH_SIZE
                        if processed % 50 == 0:
                            await status_msg.edit_text(
                                f"🔄 Progress: {processed}/{total_frames} frames\n"
                                f"📝 Found {len(subtitles)} subtitles"
                            )

            if not subtitles:
                return await status_msg.edit_text(
                    "❌ No text found in video.\n"
                    "Try with a video that has clear, visible text."
                )

            # Optimize subtitles
            optimized_subtitles = []
            current_subtitle = None
            
            for sub in subtitles:
                if not current_subtitle:
                    current_subtitle = sub
                    continue
                    
                if (sub['start_time'] - current_subtitle['end_time'] <= 1 and 
                    sub['text'] == current_subtitle['text']):
                    current_subtitle['end_time'] = sub['end_time']
                else:
                    optimized_subtitles.append(current_subtitle)
                    current_subtitle = sub
                    
            if current_subtitle:
                optimized_subtitles.append(current_subtitle)

            # Generate SRT
            srt_path = os.path.join(temp_dir, 'subtitles.srt')
            with open(srt_path, 'w', encoding='utf-8') as f:
                for i, sub in enumerate(optimized_subtitles, 1):
                    f.write(f"{i}\n")
                    f.write(f"{format_time(sub['start_time'])} --> {format_time(sub['end_time'])}\n")
                    f.write(f"{sub['text']}\n\n")

            processing_time = time.time() - start_time
            speed = total_frames / processing_time

            await message.reply_document(
                document=srt_path,
                caption=(
                    f"✅ Successfully extracted subtitles!\n"
                    f"📝 Found {len(optimized_subtitles)} subtitle sections\n"
                    f"🎞 Processed {total_frames} frames\n"
                    f"⏱ Time taken: {processing_time:.1f}s\n"
                    f"⚡️ Speed: {speed:.1f} frames/s"
                )
            )
            await status_msg.delete()

    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        if 'status_msg' in locals():
            await status_msg.edit_text(
                f"❌ Error during processing:\n{str(e)}\n"
                "Please try again or contact support."
            )
    finally:
        # Final cleanup
        gc.collect()