from bot import Bot
from pyrogram import filters
import os
import cv2
import numpy as np
import pytesseract
import tempfile
from PIL import Image
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
from config import LOGGER
import re

# Initialize logger
logger = LOGGER(__name__)

# Constants for processing
BATCH_SIZE = 5
MAX_WORKERS = 4
MIN_TEXT_LENGTH = 3
OCR_CONFIDENCE_THRESHOLD = 45
FRAME_INTERVAL = 1  # Extract 1 frame per second
MAX_DIMENSION = 1280  # Max width/height for processing

# OCR Configuration
TESSERACT_CONFIG = '--psm 6 --oem 3 -c tessedit_char_whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?-():; "\' " --dpi 300'

def format_timedelta(seconds):
    """Convert seconds to SRT timestamp format"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    milliseconds = int((seconds % 1) * 1000)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d},{milliseconds:03d}"

def optimize_image(image):
    """Optimize image for better OCR accuracy"""
    try:
        # Ensure grayscale
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Resize if too large
        height, width = image.shape
        if width > MAX_DIMENSION or height > MAX_DIMENSION:
            scale = min(MAX_DIMENSION / width, MAX_DIMENSION / height)
            new_width = int(width * scale)
            new_height = int(height * scale)
            image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)

        # Apply image enhancements
        # 1. Denoise
        denoised = cv2.fastNlMeansDenoising(image, h=10)
        
        # 2. Increase contrast using CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # 3. Adaptive thresholding
        binary = cv2.adaptiveThreshold(
            enhanced, 
            255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 
            11, 
            2
        )
        
        # 4. Remove noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
    except Exception as e:
        logger.error(f"Image optimization error: {str(e)}")
        return image

async def extract_frames(video_path, output_dir):
    """Extract frames from video with bottom quarter crop"""
    try:
        # FFmpeg command to extract frames and crop bottom quarter
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vf', f'fps={FRAME_INTERVAL},crop=iw:ih/4:0:3*ih/4,scale=\'min(1280,iw)\':-1',
            '-frame_pts', '1',
            '-vsync', '0',
            '-f', 'image2',
            os.path.join(output_dir, 'frame_%d.jpg')
        ]

        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.communicate()
        frames = [f for f in os.listdir(output_dir) if f.endswith('.jpg')]
        return len(frames)

    except Exception as e:
        logger.error(f"Frame extraction error: {str(e)}")
        raise

def clean_text(text):
    """Clean and normalize extracted text"""
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Remove lines with just numbers or special characters
    lines = text.split('\n')
    cleaned_lines = [line.strip() for line in lines if re.search('[a-zA-Z]', line)]
    
    # Join and clean final text
    text = ' '.join(cleaned_lines)
    
    # Remove non-standard characters
    text = re.sub(r'[^\x00-\x7F]+', '', text)
    
    return text.strip()

def process_frame_batch(frame_paths):
    """Process a batch of frames"""
    results = []
    
    for frame_path in frame_paths:
        try:
            # Extract frame number from filename
            frame_num = int(re.search(r'frame_(\d+)', frame_path).group(1))
            
            # Read and process image
            image = cv2.imread(frame_path)
            if image is None:
                continue

            # Optimize image
            processed = optimize_image(image)
            
            # Convert to PIL Image for better OCR handling
            pil_image = Image.fromarray(processed)
            
            # Perform OCR
            ocr_data = pytesseract.image_to_data(
                pil_image,
                lang='eng',
                config=TESSERACT_CONFIG,
                output_type=pytesseract.Output.DICT
            )

            # Extract text with confidence check
            text_parts = []
            for i, conf in enumerate(ocr_data['conf']):
                if conf > OCR_CONFIDENCE_THRESHOLD:
                    text = ocr_data['text'][i].strip()
                    if text:
                        text_parts.append(text)

            if text_parts:
                text = clean_text(' '.join(text_parts))
                if len(text) >= MIN_TEXT_LENGTH:
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
    """Handle video processing and subtitle generation"""
    try:
        # Verify video file
        if not (message.video or (message.document and 
                message.document.mime_type and 
                message.document.mime_type.startswith('video/'))):
            await message.reply_text("❌ Please send a video file.")
            return

        # Initial status message
        status_msg = await message.reply_text(
            "🎥 Starting video processing...\n"
            "⏳ This might take a few minutes"
        )
        
        start_time = time.time()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download video
            video_path = os.path.join(temp_dir, 'video.mp4')
            await message.download(
                video_path,
                progress=lambda c, t: logger.info(f"Download progress: {(c/t)*100:.1f}%")
            )

            # Create frames directory
            frames_dir = os.path.join(temp_dir, 'frames')
            os.makedirs(frames_dir, exist_ok=True)

            # Extract frames
            await status_msg.edit_text("📥 Extracting frames...")
            total_frames = await extract_frames(video_path, frames_dir)

            if total_frames == 0:
                await status_msg.edit_text("❌ No frames could be extracted from the video.")
                return

            # Process frames
            await status_msg.edit_text("🔍 Processing frames for text...")
            
            frames = sorted([f for f in os.listdir(frames_dir) if f.endswith('.jpg')])
            subtitle_data = []
            processed = 0

            # Process frames in batches
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                for i in range(0, len(frames), BATCH_SIZE):
                    batch = frames[i:i + BATCH_SIZE]
                    batch_paths = [os.path.join(frames_dir, f) for f in batch]
                    
                    results = process_frame_batch(batch_paths)
                    subtitle_data.extend(results)
                    
                    processed += len(batch)
                    if processed % 20 == 0:
                        await status_msg.edit_text(
                            f"🔄 Progress: {processed}/{total_frames} frames\n"
                            f"📝 Found text in {len(subtitle_data)} frames"
                        )

            if not subtitle_data:
                await status_msg.edit_text(
                    "❌ No text detected in video.\n"
                    "Try with a video that has clear, visible text."
                )
                return

            # Sort by frame number and merge nearby identical subtitles
            subtitle_data.sort(key=lambda x: x[0])
            merged_subtitles = []
            current = None

            for frame_num, text in subtitle_data:
                if not current:
                    current = {'start': frame_num, 'end': frame_num + 1, 'text': text}
                    continue

                if (frame_num - current['end'] <= 2 and text == current['text']):
                    current['end'] = frame_num + 1
                else:
                    merged_subtitles.append(current)
                    current = {'start': frame_num, 'end': frame_num + 1, 'text': text}

            if current:
                merged_subtitles.append(current)

            # Generate SRT file
            srt_path = os.path.join(temp_dir, 'subtitles.srt')
            with open(srt_path, 'w', encoding='utf-8') as f:
                for i, sub in enumerate(merged_subtitles, 1):
                    start_time = format_timedelta(sub['start'])
                    end_time = format_timedelta(sub['end'])
                    
                    f.write(f"{i}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{sub['text']}\n\n")

            # Calculate stats
            processing_time = time.time() - start_time
            speed = total_frames / processing_time

            # Send result
            await message.reply_document(
                document=srt_path,
                caption=(
                    f"✅ Successfully extracted subtitles!\n"
                    f"📝 Found {len(merged_subtitles)} subtitle sections\n"
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
                "Please try again with a different video."
            )