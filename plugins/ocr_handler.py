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
import shutil
import io
import mmap
from collections import deque

# Initialize logger
logger = LOGGER(__name__)

# Constants
BATCH_SIZE = 10  # Increased batch size for better throughput
MIN_TEXT_LENGTH = 3
TEXT_SIMILARITY_THRESHOLD = 0.8
SKIP_TIME = 120  # 2 minutes in seconds
MAX_WORKERS = 6  # Optimal thread count for OCR
FRAME_BUFFER_SIZE = 20  # Number of frames to buffer
OCR_CONFIDENCE_THRESHOLD = 60  # Minimum confidence for OCR text

# OCR Configuration
TESSERACT_CONFIG = '--psm 6 --oem 3 -c tessedit_char_whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?-():; " --dpi 70'

class FrameBuffer:
    def __init__(self, size=FRAME_BUFFER_SIZE):
        self.buffer = deque(maxlen=size)
        
    def add_frame(self, frame):
        self.buffer.append(frame)
        
    def get_frames(self):
        return list(self.buffer)
        
    def clear(self):
        self.buffer.clear()

def optimize_image_for_ocr(image):
    """Optimize image for better OCR accuracy"""
    try:
        # Convert to grayscale if not already
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Apply advanced image preprocessing
        # 1. Denoise
        denoised = cv2.fastNlMeansDenoising(gray)
        
        # 2. Increase contrast using CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        contrasted = clahe.apply(denoised)
        
        # 3. Thresholding
        _, thresh = cv2.threshold(contrasted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 4. Remove small noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        return cleaned
    except Exception as e:
        logger.error(f"Image optimization failed: {str(e)}")
        return image

async def extract_frames_efficiently(video_path, output_dir, start_time=SKIP_TIME, status_msg=None):
    """Extract frames with maximum efficiency"""
    try:
        logger.info(f"Starting optimized frame extraction from: {start_time}s")
        
        # Optimize FFmpeg command for speed
        ffmpeg_cmd = [
            'ffmpeg',
            '-hwaccel', 'auto',  # Auto-select hardware acceleration
            '-ss', str(start_time),  # Seek position
            '-i', video_path,
            '-vf', 'fps=1,crop=iw:ih/4:0:3*ih/4',  # Extract bottom quarter
            '-frame_pts', '1',
            '-vsync', '0',  # Disable video sync
            '-f', 'image2pipe',  # Output to pipe
            '-pix_fmt', 'gray',  # Direct grayscale output
            '-vcodec', 'rawvideo',  # Raw video output
            '-'  # Output to pipe
        ]

        # Start FFmpeg process
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=10**8  # Large buffer
        )

        frame_buffer = FrameBuffer()
        frame_count = 0
        
        # Read frames directly from pipe
        while True:
            # Read raw frame data
            frame_size = process.stdout.read(1)
            if not frame_size:
                break
                
            frame_data = process.stdout.read(int.from_bytes(frame_size, 'big'))
            if not frame_data:
                break
                
            # Convert to numpy array
            frame = np.frombuffer(frame_data, dtype=np.uint8)
            if frame.size == 0:
                continue
                
            # Save frame
            frame_path = os.path.join(output_dir, f'frame_{frame_count}.jpg')
            cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            
            frame_count += 1
            if frame_count % 30 == 0 and status_msg:
                await status_msg.edit(f"Extracted {frame_count} frames...")

        return frame_count

    except Exception as e:
        logger.error(f"Frame extraction error: {str(e)}")
        raise

def process_frame_batch(frames):
    """Process a batch of frames efficiently"""
    results = []
    
    for frame_path in frames:
        try:
            # Read image using memory mapping
            with open(frame_path, 'rb') as f:
                mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
                img_array = np.frombuffer(mm, dtype=np.uint8)
                image = cv2.imdecode(img_array, cv2.IMREAD_GRAYSCALE)
                mm.close()

            if image is None:
                continue

            # Optimize image
            optimized = optimize_image_for_ocr(image)

            # OCR with confidence check
            ocr_data = pytesseract.image_to_data(
                optimized,
                lang='eng',
                config=TESSERACT_CONFIG,
                output_type=pytesseract.Output.DICT
            )

            # Filter by confidence
            text_parts = []
            for i, conf in enumerate(ocr_data['conf']):
                if conf > OCR_CONFIDENCE_THRESHOLD:
                    text_parts.append(ocr_data['text'][i])

            text = ' '.join(text_parts).strip()
            
            if len(text) >= MIN_TEXT_LENGTH:
                results.append(text)

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
    start_time = time.time()
    try:
        if not (message.video or (message.document and message.document.mime_type and 
                                message.document.mime_type.startswith('video/'))):
            return

        logger.info("Starting video processing")
        status_msg = await message.reply_text("Initializing video processing...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download video efficiently
            video_path = os.path.join(temp_dir, 'video.mp4')
            await message.download(
                video_path,
                progress=lambda c, t: logger.info(f"Download progress: {(c/t)*100:.1f}%")
            )

            frames_dir = os.path.join(temp_dir, 'frames')
            os.makedirs(frames_dir, exist_ok=True)

            # Extract frames
            await status_msg.edit("Extracting frames...")
            total_frames = await extract_frames_efficiently(video_path, frames_dir, SKIP_TIME, status_msg)

            if total_frames == 0:
                return await status_msg.edit("No frames could be extracted.")

            # Process frames in optimized batches
            frames = sorted([f for f in os.listdir(frames_dir) if f.endswith('.jpg')])
            subtitles = []
            processed = 0

            await status_msg.edit("Processing frames...")

            # Process frames in parallel with larger batches
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
                            await status_msg.edit(
                                f"Processing: {processed}/{total_frames} frames\n"
                                f"Found {len(subtitles)} subtitles"
                            )
                    except Exception as e:
                        logger.error(f"Batch processing error: {str(e)}")

            if not subtitles:
                return await status_msg.edit("No subtitles found.")

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

            # Send result
            processing_time = time.time() - start_time
            await message.reply_document(
                document=srt_path,
                caption=(
                    f"✅ Extracted {len(optimized_subtitles)} subtitles\n"
                    f"🎞 Processed {total_frames} frames\n"
                    f"⏱ Processing time: {processing_time:.1f}s\n"
                    f"⚡️ Speed: {total_frames/processing_time:.1f} frames/s"
                )
            )
            await status_msg.delete()

    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        if 'status_msg' in locals():
            await status_msg.edit(f"Error: {str(e)}")