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
from pathlib import Path
import json

# Initialize logger
logger = LOGGER(__name__)

# Constants
MAX_WORKERS = 4
FRAME_BATCH = 30
CACHE_DIR = "cache"
BATCH_SIZE = 1000  # Number of frames to process before saving progress

# OCR Configuration
OCR_CONFIG = '--psm 6 --oem 1 -l chi_sim+eng --dpi 300'
os.environ['TESSDATA_PREFIX'] = '/usr/share/tesseract-ocr/4.00/tessdata'

class FrameGenerator:
    def __init__(self, video_path, output_dir):
        self.video_path = video_path
        self.output_dir = output_dir
        self.current_batch = 0
        
    async def extract_batch(self, start_time):
        """Extract a batch of frames using FFmpeg copy method"""
        try:
            batch_dir = os.path.join(self.output_dir, f"batch_{self.current_batch}")
            os.makedirs(batch_dir, exist_ok=True)
            
            # Use FFmpeg copy method for faster extraction
            cmd = [
                'ffmpeg',
                '-ss', str(start_time),
                '-t', str(BATCH_SIZE),  # Duration for this batch
                '-i', self.video_path,
                '-c:v', 'copy',  # Use copy method for faster processing
                '-vf', (
                    'fps=1,'  # 1 frame per second
                    'crop=iw:ih/4:0:3*ih/4,'  # Bottom quarter
                    'scale=w=trunc(min(iw,1280)/2)*2:h=-2'  # Efficient scaling
                ),
                '-vsync', '0',
                '-frame_pts', '1',
                os.path.join(batch_dir, 'frame_%d.jpg')
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            frames = sorted(Path(batch_dir).glob('*.jpg'))
            logger.info(f"Extracted batch {self.current_batch} with {len(frames)} frames")
            self.current_batch += 1
            return frames
        
        except Exception as e:
            logger.error(f"Batch extraction error: {str(e)}")
            return []

class TextProcessor:
    def __init__(self, cache_file):
        self.cache_file = cache_file
        self.results = self.load_cache()
        
    def load_cache(self):
        """Load existing results from cache"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Cache loading error: {str(e)}")
        return []

    def save_cache(self):
        """Save results to cache"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Cache saving error: {str(e)}")

    def enhance_image(self, image):
        """Enhanced image processing for anime subtitles"""
        try:
            # Convert to LAB color space for better processing
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # Apply CLAHE with higher clip limit for anime
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            enhanced_l = clahe.apply(l)
            
            # Merge channels
            enhanced_lab = cv2.merge([enhanced_l, a, b])
            enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
            
            # Convert to grayscale
            gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
            
            # Multi-threshold approach for white text
            _, binary1 = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
            
            return binary1
        except Exception as e:
            logger.error(f"Image enhancement error: {str(e)}")
            return image

    def process_frame(self, frame_path):
        """Process a single frame"""
        try:
            frame_num = int(frame_path.stem.split('_')[1])
            
            # Read image
            image = cv2.imread(str(frame_path))
            if image is None:
                return None
            
            # Enhance image
            processed = self.enhance_image(image)
            
            # OCR with confidence check
            ocr_data = pytesseract.image_to_data(
                processed,
                config=OCR_CONFIG,
                output_type=pytesseract.Output.DICT
            )
            
            # Extract text with confidence
            text_parts = []
            for i, (conf, text) in enumerate(zip(ocr_data['conf'], ocr_data['text'])):
                if conf > 30 and text.strip():  # Lower threshold for anime
                    text_parts.append(text.strip())
            
            if text_parts:
                text = ' '.join(text_parts)
                logger.info(f"Frame {frame_num}: Found text: {text[:50]}...")
                return {'frame': frame_num, 'text': text}
            
            return None
            
        except Exception as e:
            logger.error(f"Frame processing error: {str(e)}")
            return None
        finally:
            try:
                frame_path.unlink()  # Remove processed frame
            except:
                pass

@Bot.on_message(filters.video | filters.document)
async def process_video(client, message):
    try:
        logger.info("Starting video processing")
        status_msg = await message.reply_text("🎥 Processing video...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup paths
            video_path = os.path.join(temp_dir, 'video.mp4')
            frames_dir = os.path.join(temp_dir, 'frames')
            cache_file = os.path.join(CACHE_DIR, f"{message.id}.json")
            
            # Download video
            await message.download(video_path)
            os.makedirs(frames_dir, exist_ok=True)
            
            # Initialize processors
            frame_gen = FrameGenerator(video_path, frames_dir)
            text_proc = TextProcessor(cache_file)
            
            # Process video in batches
            current_time = 0
            while True:
                # Extract batch of frames
                frames = await frame_gen.extract_batch(current_time)
                if not frames:
                    break
                
                # Process frames
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    for i in range(0, len(frames), FRAME_BATCH):
                        batch = frames[i:i + FRAME_BATCH]
                        futures = [executor.submit(text_proc.process_frame, frame) for frame in batch]
                        
                        # Collect results
                        for future in futures:
                            result = future.result()
                            if result:
                                text_proc.results.append(result)
                        
                        # Update progress
                        await status_msg.edit_text(
                            f"🔄 Processing batch {frame_gen.current_batch}\n"
                            f"📝 Found text in {len(text_proc.results)} frames"
                        )
                
                # Save progress
                text_proc.save_cache()
                current_time += BATCH_SIZE
            
            # Generate SRT
            srt_path = os.path.join(temp_dir, 'subtitles.srt')
            with open(srt_path, 'w', encoding='utf-8') as f:
                for i, result in enumerate(sorted(text_proc.results, key=lambda x: x['frame']), 1):
                    f.write(f"{i}\n")
                    f.write(f"{format_time(result['frame'])} --> {format_time(result['frame'] + 1)}\n")
                    f.write(f"{result['text']}\n\n")
            
            # Send result
            await message.reply_document(
                document=srt_path,
                caption=f"📝 Found subtitles in {len(text_proc.results)} frames"
            )
            
            await status_msg.delete()
            logger.info("Video processing completed")
            
    except Exception as e:
        error_msg = f"Processing error: {str(e)}"
        logger.error(error_msg)
        await message.reply_text(error_msg)

def format_time(seconds):
    """Convert seconds to SRT timestamp format"""
    hrs = seconds // 3600
    mins = (seconds % 3600) // 60
    secs = seconds % 60
    ms = int((seconds % 1) * 1000)
    return f"{int(hrs):02d}:{int(mins):02d}:{int(secs):02d},{ms:03d}"