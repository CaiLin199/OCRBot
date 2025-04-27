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
MAX_WORKERS = int(os.getenv('MAX_WORKERS', '4'))
FRAME_BATCH = int(os.getenv('FRAME_BATCH', '30'))
TEMP_ROOT = '/tmp/ocr_cache'
SAVE_INTERVAL = 50  # Save progress every 50 frames

# OCR Configuration
OCR_CONFIG = '--psm 6 --oem 1 -l chi_sim+eng --dpi 300'
os.environ['TESSDATA_PREFIX'] = '/usr/share/tesseract-ocr/4.00/tessdata'

class StreamingFrameExtractor:
    def __init__(self, video_path):
        self.video_path = video_path
        self.current_position = 0
        
    async def get_duration(self):
        """Get video duration using FFprobe"""
        cmd = [
            'ffprobe', '-v', 'error', 
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            self.video_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        return float(stdout.decode().strip())

    async def extract_frames(self):
        """Stream frames using FFmpeg with copy method"""
        try:
            cmd = [
                'ffmpeg',
                '-ss', str(self.current_position),
                '-i', self.video_path,
                '-c:v', 'copy',  # Use copy method for faster processing
                '-vf', (
                    'fps=1,'  # 1 frame per second
                    'crop=iw:ih/4:0:3*ih/4,'  # Crop bottom quarter
                    'scale=w=trunc(min(iw,1280)/2)*2:h=-2,'  # Efficient scaling
                    'eq=contrast=1.3:brightness=0.1:saturation=1.5'  # Enhance for subtitles
                ),
                '-f', 'image2pipe',
                '-pix_fmt', 'bgr24',
                '-vcodec', 'rawvideo',
                'pipe:'
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            frame_size = 1280 * 180 * 3  # width * height * channels
            while True:
                frame_data = await process.stdout.read(frame_size)
                if not frame_data:
                    break
                    
                frame = np.frombuffer(frame_data, dtype=np.uint8)
                frame = frame.reshape((180, 1280, 3))
                
                yield self.current_position, frame
                self.current_position += 1
                
        except Exception as e:
            logger.error(f"Frame extraction error: {e}")
            raise

def enhance_frame(frame):
    """Optimize frame for OCR"""
    try:
        # Convert to LAB color space
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Enhance lightness channel
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced_l = clahe.apply(l)
        
        # Merge channels
        enhanced_lab = cv2.merge([enhanced_l, a, b])
        enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
        
        # Convert to grayscale
        gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
        
        # Apply adaptive threshold
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        
        return binary
    except Exception as e:
        logger.error(f"Frame enhancement error: {e}")
        return frame

async def process_frame(frame_data):
    """Process a single frame"""
    position, frame = frame_data
    try:
        # Enhance frame
        processed = enhance_frame(frame)
        
        # OCR with confidence check
        ocr_data = pytesseract.image_to_data(
            processed,
            config=OCR_CONFIG,
            output_type=pytesseract.Output.DICT
        )
        
        # Extract text parts with confidence
        text_parts = []
        for i, (conf, text) in enumerate(zip(ocr_data['conf'], ocr_data['text'])):
            if conf > 30 and text.strip():  # Lower threshold for anime
                text_parts.append(text.strip())
        
        if text_parts:
            text = ' '.join(text_parts)
            logger.info(f"Position {position}: Found text: {text[:50]}...")
            return position, text
            
        return None
        
    except Exception as e:
        logger.error(f"Frame processing error at position {position}: {e}")
        return None

def format_time(seconds):
    """Convert seconds to SRT timestamp format"""
    hrs = seconds // 3600
    mins = (seconds % 3600) // 60
    secs = seconds % 60
    ms = int((seconds % 1) * 1000)
    return f"{int(hrs):02d}:{int(mins):02d}:{int(secs):02d},{ms:03d}"

@Bot.on_message(filters.video | filters.document)
async def process_video(client, message):
    try:
        logger.info(f"Starting video processing for message {message.id}")
        status_msg = await message.reply_text("🎥 Processing video...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download video
            video_path = os.path.join(temp_dir, 'video.mp4')
            await message.download(video_path)
            logger.info("Video downloaded successfully")
            
            # Initialize frame extractor
            extractor = StreamingFrameExtractor(video_path)
            duration = await extractor.get_duration()
            
            # Process frames
            subtitles = []
            processed_frames = 0
            
            async for frame_data in extractor.extract_frames():
                try:
                    # Process frame
                    result = await process_frame(frame_data)
                    if result:
                        position, text = result
                        subtitles.append((position, text))
                    
                    # Update progress
                    processed_frames += 1
                    if processed_frames % 10 == 0:  # Update every 10 frames
                        progress = (processed_frames / duration) * 100
                        await status_msg.edit_text(
                            f"🔄 Processing: {progress:.1f}%\n"
                            f"📝 Found subtitles: {len(subtitles)}"
                        )
                    
                except Exception as e:
                    logger.error(f"Error processing frame: {e}")
                    continue
            
            # Generate SRT
            if subtitles:
                srt_path = os.path.join(temp_dir, 'subtitles.srt')
                with open(srt_path, 'w', encoding='utf-8') as f:
                    for i, (pos, text) in enumerate(sorted(subtitles), 1):
                        f.write(f"{i}\n")
                        f.write(f"{format_time(pos)} --> {format_time(pos + 1)}\n")
                        f.write(f"{text}\n\n")
                
                # Send result
                await message.reply_document(
                    document=srt_path,
                    caption=f"📝 Extracted {len(subtitles)} subtitles from {processed_frames} frames"
                )
            else:
                await message.reply_text("Processing completed but no clear subtitles were detected. Try adjusting the video quality.")
            
            await status_msg.delete()
            logger.info(f"Video processing completed. Found {len(subtitles)} subtitles")
            
    except Exception as e:
        error_msg = f"Processing error: {str(e)}"
        logger.error(error_msg)
        await message.reply_text(error_msg)