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
FRAME_BATCH = 30  # Process 30 frames at once for better I/O
THRESHOLD_AREA = 50  # Minimum text area size
GPU_ACCELERATION = '-hwaccel cuda -hwaccel_output_format cuda' if cv2.cuda.getCudaEnabledDeviceCount() > 0 else ''

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
        # Get video duration first
        probe_cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *probe_cmd,
            stdout=asyncio.subprocess.PIPE
        )
        duration_output = await process.communicate()
        duration = float(duration_output[0].decode().strip())
        
        # Optimized FFmpeg command with GPU acceleration and efficient filtering
        cmd = [
            'ffmpeg',
            *GPU_ACCELERATION.split(),
            '-i', video_path,
            '-vf', (
                'fps=1,'  # 1 frame per second
                'crop=iw:ih/4:0:3*ih/4,'  # crop bottom quarter
                'scale=w=trunc(min(iw,1280)/2)*2:h=-2,'  # scale efficiently
                'eq=contrast=1.2:brightness=0.1'  # enhance contrast
            ),
            '-sws_flags', 'lanczos',  # high quality scaling
            '-start_number', '0',
            '-vsync', '0',
            '-f', 'image2pipe',  # pipe output for faster processing
            '-vcodec', 'ppm',  # use PPM format for faster decoding
            'pipe:'
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Process frames in memory
        frame_data = await process.communicate()
        frames = frame_data[0].split(b'P6\n')[1:]  # Split PPM frames
        
        # Save frames
        for i, frame in enumerate(frames):
            frame_path = os.path.join(output_dir, f'frame_{i}.jpg')
            with open(frame_path, 'wb') as f:
                f.write(frame)
        
        return len(frames)

    except Exception as e:
        logger.error(f"Frame extraction error: {str(e)}")
        raise

def enhance_image(image):
    """Advanced image enhancement for better OCR"""
    try:
        # Convert to float and normalize
        img_float = image.astype(np.float32) / 255.0
        
        # Apply CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(cv2.convertScaleAbs(img_float * 255))
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(enhanced)
        
        # Sharpen
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(denoised, -1, kernel)
        
        # Binarize using Otsu's method
        _, binary = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
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
            
            # Read image
            image = cv2.imread(frame_path, cv2.IMREAD_GRAYSCALE)
            if image is None:
                continue
            
            # Enhance image
            processed = enhance_image(image)
            
            # Find text regions (optimize for Chinese characters)
            mser = cv2.MSER_create(
                _min_area=100,
                _max_area=5000,
                _delta=10
            )
            regions, _ = mser.detectRegions(processed)
            
            if regions:
                # Create mask of text regions
                mask = np.zeros(processed.shape, dtype=np.uint8)
                for region in regions:
                    hull = cv2.convexHull(region.reshape(-1, 1, 2))
                    cv2.drawContours(mask, [hull], -1, (255), -1)
                
                # Apply mask
                text_regions = cv2.bitwise_and(processed, processed, mask=mask)
                
                # OCR with confidence check
                text = pytesseract.image_to_string(
                    text_regions,
                    config=OCR_CONFIG
                ).strip()
                
                if text:
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
            
            # Process frames in batches
            await status_msg.edit_text("🔍 Processing frames...")
            all_frames = sorted([os.path.join(frames_dir, f) for f in os.listdir(frames_dir)])
            
            all_results = []
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                for i in range(0, len(all_frames), FRAME_BATCH):
                    batch = all_frames[i:i + FRAME_BATCH]
                    results = executor.submit(process_frame_batch, batch).result()
                    all_results.extend(results)
                    
                    # Update progress
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