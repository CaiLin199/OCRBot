import os
import asyncio
import subprocess
import shutil
import easyocr
import cv2
import numpy as np
from pyrogram import Client, filters
from pyrogram.types import Message
from bot import Bot
from config import LOGGER
import tempfile

# OCR Reader Setup
reader = easyocr.Reader(['ch_sim'], gpu=False, download_enabled=False)

# Increased frame rate for better timing accuracy
FRAME_RATE = 10  # frames per second

def detect_text_area(frame):
    """Detect if there's text by checking pixel changes in the bottom area"""
    try:
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Focus on bottom third of the frame where subtitles usually appear
        height = gray.shape[0]
        bottom_area = gray[int(height*0.6):, :]
        
        # Apply threshold
        _, thresh = cv2.threshold(bottom_area, 180, 255, cv2.THRESH_BINARY)
        
        # Count white pixels (text pixels)
        white_pixel_count = np.sum(thresh == 255)
        
        # If significant white pixels found, consider it as text
        return white_pixel_count > (thresh.size * 0.01)  # 1% threshold
    except:
        return False

def get_precise_timestamp(frames_data, idx, direction='forward'):
    """
    Get precise timestamp by checking neighboring frames
    direction: 'forward' for subtitle start, 'backward' for subtitle end
    """
    frame_time = 1/FRAME_RATE
    current_idx = idx
    
    if direction == 'forward':
        # Look backward to find exact start
        while current_idx > 0:
            if not frames_data[current_idx-1]['has_text']:
                break
            current_idx -= 1
    else:
        # Look forward to find exact end
        while current_idx < len(frames_data)-1:
            if not frames_data[current_idx+1]['has_text']:
                break
            current_idx += 1
    
    return current_idx * frame_time

@Bot.on_message(filters.video | filters.document)
async def extract_hardsub(_, message: Message):
    try:
        status_msg = await message.reply_text("🎥 Processing video...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download video
            video_path = os.path.join(temp_dir, "video.mp4")
            await message.download(file_name=video_path)
            LOGGER.info(f"Downloaded: {video_path}")
            
            frames_dir = os.path.join(temp_dir, "frames")
            os.makedirs(frames_dir, exist_ok=True)
            
            # Extract frames with higher rate for better timing
            cmd = [
                "ffmpeg", "-i", video_path,
                "-vf", f"fps={FRAME_RATE}",
                "-frame_pts", "1",
                f"{frames_dir}/frame_%05d.jpg"
            ]
            
            await status_msg.edit_text("⚙️ Extracting frames...")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            
            # Get all frames and analyze them
            frames = sorted(glob(f"{frames_dir}/*.jpg"))
            frames_data = []
            
            await status_msg.edit_text("🔍 Analyzing frames...")
            
            # First pass: Detect text presence
            for idx, frame_path in enumerate(frames):
                if idx % 20 == 0:  # Update progress every 20 frames
                    progress = (idx / len(frames)) * 100
                    await status_msg.edit_text(f"🔍 Analyzing frames: {progress:.1f}%")
                
                frame = cv2.imread(frame_path)
                has_text = detect_text_area(frame)
                frames_data.append({
                    'path': frame_path,
                    'has_text': has_text,
                    'text': None
                })
            
            # Find segments with text
            segments = []
            in_text_segment = False
            segment_start = 0
            
            for idx, frame_data in enumerate(frames_data):
                if frame_data['has_text'] and not in_text_segment:
                    segment_start = idx
                    in_text_segment = True
                elif not frame_data['has_text'] and in_text_segment:
                    # Found a segment, get precise timestamps
                    start_time = get_precise_timestamp(frames_data, segment_start, 'forward')
                    end_time = get_precise_timestamp(frames_data, idx-1, 'backward')
                    segments.append((segment_start, idx-1, start_time, end_time))
                    in_text_segment = False
            
            # Handle last segment if exists
            if in_text_segment:
                start_time = get_precise_timestamp(frames_data, segment_start, 'forward')
                end_time = get_precise_timestamp(frames_data, len(frames_data)-1, 'backward')
                segments.append((segment_start, len(frames_data)-1, start_time, end_time))
            
            # Process segments for text
            subtitles = []
            await status_msg.edit_text("📝 Extracting text from segments...")
            
            for idx, (start_idx, end_idx, start_time, end_time) in enumerate(segments):
                # Use middle frame of segment for OCR
                mid_idx = (start_idx + end_idx) // 2
                frame_path = frames_data[mid_idx]['path']
                
                # OCR on middle frame
                result = reader.readtext(frame_path, detail=0)
                text = " ".join(result).strip()
                
                if text:
                    subtitles.append((start_time, end_time, text))
                
                # Update progress
                progress = (idx / len(segments)) * 100
                await status_msg.edit_text(f"📝 Extracting text: {progress:.1f}%")
                
                # Clean up frame immediately
                os.remove(frame_path)
            
            # Create SRT file
            srt_path = os.path.join(temp_dir, "subtitles.srt")
            srt_content = create_srt(subtitles)
            
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
            
            # Send file
            if subtitles:
                await message.reply_document(
                    document=srt_path,
                    caption=f"📝 Extracted {len(subtitles)} subtitles"
                )
            else:
                await message.reply_text("⚠️ No subtitles detected in the video")
            
            await status_msg.delete()
            LOGGER.info("Process completed")
            
    except Exception as e:
        error_msg = f"Processing error: {str(e)}"
        LOGGER.error(error_msg)
        await message.reply_text(f"❌ {error_msg}")

def create_srt(subtitles):
    srt_text = ""
    for idx, (start, end, text) in enumerate(subtitles, 1):
        srt_text += f"{idx}\n"
        srt_text += f"{format_timestamp(start)} --> {format_timestamp(end)}\n"
        srt_text += f"{text}\n\n"
    return srt_text

def format_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"