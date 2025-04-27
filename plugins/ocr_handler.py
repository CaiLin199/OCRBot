'''Create a Python Telegram bot that processes a video, extracts the bottom 1/4th of the video frames, and performs OCR on these cropped frames. Generate accurate timestamps for subtitles, format them into a .srt file, and send this subtitle file back to the user. Clean all temporary files during and after the process. Ensure that the bot is efficient, fast, and works within a small memory/CPU space (ideal for hosting on Koyeb).'''




from bot import Bot
from pyrogram import filters  # Add this import
import os
import cv2
import numpy as np
import pytesseract
import tempfile
from moviepy.editor import VideoFileClip

# Document filter using lambda for better control
document_filter = lambda _, __, msg: bool(msg.document and msg.document.mime_type and 
                                        msg.document.mime_type.startswith('video/'))
video_filter = lambda _, __, msg: bool(msg.video)

@Bot.on_message(filters.create(document_filter) | filters.create(video_filter))
async def process_video(client, message):
    try:
        await message.reply_text("Starting video processing. Please wait...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download file
            video_path = os.path.join(temp_dir, 'video.mp4')
            await message.download(video_path)
            
            if not os.path.exists(video_path):
                return await message.reply_text("Failed to download video.")
            
            # Process video and generate subtitles
            srt_path = await extract_subtitles(video_path, temp_dir)
            
            if os.path.exists(srt_path):
                await message.reply_document(
                    document=srt_path,
                    caption="Here are your extracted subtitles!"
                )
            else:
                await message.reply_text("No subtitles were found in the video.")
                
    except Exception as e:
        await message.reply_text(f'Error processing video: {str(e)}')

async def extract_subtitles(video_path, temp_dir):
    subtitles = []
    video = cv2.VideoCapture(video_path)
    fps = video.get(cv2.CAP_PROP_FPS)
    total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Process every frame to ensure no subtitles are missed
    current_frame = 0
    last_text = ""
    text_duration = 0
    
    while current_frame < total_frames:
        video.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
        ret, frame = video.read()
        
        if not ret:
            break
            
        # Extract bottom quarter of the frame precisely
        height = frame.shape[0]
        width = frame.shape[1]
        crop_height = height // 4  # Exact quarter height
        bottom_quarter = frame[height - crop_height:height, 0:width]
        
        # Enhanced preprocessing for better OCR
        gray = cv2.cvtColor(bottom_quarter, cv2.COLOR_BGR2GRAY)
        # Apply adaptive thresholding for better text detection
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Denoise the image
        denoised = cv2.fastNlMeansDenoising(binary)
        
        # Perform OCR with improved configuration
        text = pytesseract.image_to_string(
            denoised,
            lang='eng',
            config='--psm 6 --oem 3'  # Assume uniform text block
        ).strip()
        
        timestamp = current_frame / fps
        
        if text:
            if text != last_text:  # New text found
                if last_text:  # Save previous subtitle
                    subtitles.append({
                        'start_time': timestamp - text_duration,
                        'end_time': timestamp,
                        'text': last_text
                    })
                last_text = text
                text_duration = 0
            text_duration += 1/fps
        elif last_text:  # Text ended
            subtitles.append({
                'start_time': timestamp - text_duration,
                'end_time': timestamp,
                'text': last_text
            })
            last_text = ""
            text_duration = 0
            
        current_frame += 1
    
    # Add final subtitle if exists
    if last_text:
        subtitles.append({
            'start_time': (total_frames/fps) - text_duration,
            'end_time': total_frames/fps,
            'text': last_text
        })
    
    video.release()
    
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
        milliseconds = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, subtitle in enumerate(subtitles, 1):
            f.write(f"{i}\n")
            f.write(f"{format_time(subtitle['start_time'])} --> {format_time(subtitle['end_time'])}\n")
            f.write(f"{subtitle['text']}\n\n")
    
    return output_path