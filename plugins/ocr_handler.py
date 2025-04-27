'''Create a Python Telegram bot that processes a video, extracts the bottom 1/4th of the video frames, and performs OCR on these cropped frames. Generate accurate timestamps for subtitles, format them into a .srt file, and send this subtitle file back to the user. Clean all temporary files during and after the process. Ensure that the bot is efficient, fast, and works within a small memory/CPU space (ideal for hosting on Koyeb).'''



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

document_filter = lambda _, __, msg: bool(msg.document and msg.document.mime_type and 
                                        msg.document.mime_type.startswith('video/'))
video_filter = lambda _, __, msg: bool(msg.video)

def humanbytes(size):
    if not size:
        return "0B"
    power = 2**10
    n = 0
    Dic_powerN = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'

@Bot.on_message(filters.create(document_filter) | filters.create(video_filter))
async def process_video(client, message):
    try:
        status_msg = await message.reply_text("Starting video processing...")
        start_time = time.time()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download file
            video_path = os.path.join(temp_dir, 'video.mp4')
            await status_msg.edit("📥 Downloading video...")
            
            try:
                # Get file size for logging
                file_size = message.document.file_size if message.document else message.video.file_size
                await LOGGER.send_message(
                    f"Starting download for {message.from_user.first_name} ({message.from_user.id})\n"
                    f"File size: {humanbytes(file_size)}"
                )
                
                await message.download(video_path)
                download_time = time.time() - start_time
                await LOGGER.send_message(
                    f"Video downloaded in {download_time:.1f}s\n"
                    f"Speed: {humanbytes(file_size/download_time)}/s"
                )
            except Exception as e:
                await LOGGER.send_message(f"Download failed: {str(e)}")
                return await status_msg.edit("Failed to download video.")
            
            if not os.path.exists(video_path):
                await LOGGER.send_message("Video download failed: File not found")
                return await status_msg.edit("Failed to download video.")
            
            # Process video and generate subtitles
            await status_msg.edit("🔍 Processing video and extracting subtitles...")
            srt_path = await extract_subtitles(video_path, temp_dir, status_msg)
            
            if os.path.exists(srt_path):
                await status_msg.edit("📤 Uploading subtitles...")
                await message.reply_document(
                    document=srt_path,
                    caption="Here are your extracted subtitles!"
                )
                await status_msg.delete()
                total_time = time.time() - start_time
                await LOGGER.send_message(
                    f"✅ Process completed for {message.from_user.first_name} ({message.from_user.id})\n"
                    f"Total time: {total_time:.1f}s"
                )
            else:
                await status_msg.edit("No subtitles were found in the video.")
                await LOGGER.send_message(f"No subtitles found in video from {message.from_user.first_name}")
                
    except Exception as e:
        error_msg = f'Error processing video: {str(e)}'
        await LOGGER.send_message(f"Error: {error_msg}\nUser: {message.from_user.first_name}")
        await message.reply_text(error_msg)

async def extract_subtitles(video_path, temp_dir, status_msg):
    subtitles = []
    frames_dir = os.path.join(temp_dir, 'frames')
    os.makedirs(frames_dir, exist_ok=True)
    
    # Extract video duration and fps using ffprobe
    try:
        probe = subprocess.run([
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=duration,r_frame_rate',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ], capture_output=True, text=True)
        
        duration, fps_str = probe.stdout.strip().split('\n')
        # Handle fractional fps like "25/1"
        if '/' in fps_str:
            num, den = map(int, fps_str.split('/'))
            fps = num / den
        else:
            fps = float(fps_str)
            
        total_frames = int(float(duration) * fps)
        await LOGGER.send_message(
            f"📊 Video Info:\n"
            f"Duration: {float(duration):.1f}s\n"
            f"FPS: {fps}\n"
            f"Total frames: {total_frames}"
        )
        
    except Exception as e:
        await LOGGER.send_message(f"Error getting video info: {str(e)}")
        return None
    
    try:
        # Extract frames using ffmpeg (1 frame per second)
        extract_start = time.time()
        subprocess.run([
            'ffmpeg', '-i', video_path,
            '-vf', f'fps=1,crop=iw:ih/4:0:3*ih/4',  # Extract bottom quarter
            '-frame_pts', '1',
            os.path.join(frames_dir, 'frame_%d.jpg')
        ])
        
        extract_time = time.time() - extract_start
        await LOGGER.send_message(f"Frames extracted in {extract_time:.1f}s")
        
        # Process extracted frames
        total_frames = len([f for f in os.listdir(frames_dir) if f.endswith('.jpg')])
        processed_frames = 0
        last_text = ""
        ocr_start = time.time()
        last_log = time.time()
        
        for i in range(total_frames):
            frame_path = os.path.join(frames_dir, f'frame_{i+1}.jpg')
            if not os.path.exists(frame_path):
                continue
                
            try:
                # Read frame and perform OCR
                image = Image.open(frame_path)
                text = pytesseract.image_to_string(
                    image,
                    lang='eng',
                    config='--psm 6 --oem 3'
                ).strip()
                
                if text and text != last_text:
                    subtitles.append({
                        'start_time': i,
                        'end_time': i + 1,
                        'text': text
                    })
                    last_text = text
                
                processed_frames += 1
                current_time = time.time()
                
                # Log progress every 5 seconds
                if current_time - last_log >= 5:
                    await LOGGER.send_message(
                        f"OCR Progress: {processed_frames}/{total_frames} frames "
                        f"({(processed_frames/total_frames*100):.1f}%)"
                    )
                    last_log = current_time
                    
            except Exception as e:
                await LOGGER.send_message(f"Error processing frame {i}: {str(e)}")
            finally:
                os.remove(frame_path)
        
        ocr_time = time.time() - ocr_start
        await LOGGER.send_message(
            f"✅ OCR completed:\n"
            f"Processed {processed_frames} frames in {ocr_time:.1f}s\n"
            f"Found {len(subtitles)} subtitle entries\n"
            f"Speed: {processed_frames/ocr_time:.1f} frames/s"
        )
        
    except Exception as e:
        await LOGGER.send_message(f"Error in frame extraction/OCR: {str(e)}")
        return None
    
    if not subtitles:
        return None
        
    # Generate SRT file
    srt_path = os.path.join(temp_dir, 'subtitles.srt')
    await generate_srt(subtitles, srt_path)
    
    return srt_path

async def generate_srt(subtitles, output_path):
    def format_time(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        milliseconds = 0
        return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, subtitle in enumerate(subtitles, 1):
                f.write(f"{i}\n")
                f.write(f"{format_time(subtitle['start_time'])} --> {format_time(subtitle['end_time'])}\n")
                f.write(f"{subtitle['text']}\n\n")
        
        await LOGGER.send_message(f"Generated SRT file with {len(subtitles)} entries")
        
    except Exception as e:
        await LOGGER.send_message(f"Error generating SRT file: {str(e)}")
        return None
    
    return output_path