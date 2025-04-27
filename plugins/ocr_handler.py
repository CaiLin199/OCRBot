'''Create a Python Telegram bot that processes a video, extracts the bottom 1/4th of the video frames, and performs OCR on these cropped frames. Generate accurate timestamps for subtitles, format them into a .srt file, and send this subtitle file back to the user. Clean all temporary files during and after the process. Ensure that the bot is efficient, fast, and works within a small memory/CPU space (ideal for hosting on Koyeb).'''



from bot import Bot
from pyrogram import filters
import os
import subprocess
import numpy as np
import pytesseract
import tempfile
from PIL import Image

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
    frames_dir = os.path.join(temp_dir, 'frames')
    os.makedirs(frames_dir, exist_ok=True)
    
    # Extract video duration and fps using ffprobe
    probe = subprocess.run([
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=duration,r_frame_rate',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ], capture_output=True, text=True)
    
    duration, fps = probe.stdout.strip().split('\n')
    fps = eval(fps)  # Evaluate fraction if needed
    total_frames = int(float(duration) * fps)
    
    # Extract frames using ffmpeg (1 frame per second)
    subprocess.run([
        'ffmpeg', '-i', video_path,
        '-vf', f'fps=1,crop=iw:ih/4:0:3*ih/4',  # Extract bottom quarter
        '-frame_pts', '1',  # Include presentation timestamp
        os.path.join(frames_dir, 'frame_%d.jpg')
    ])
    
    # Process extracted frames
    last_text = ""
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
                
        except Exception as e:
            print(f"Error processing frame {i}: {str(e)}")
        finally:
            # Clean up frame
            os.remove(frame_path)
    
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
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, subtitle in enumerate(subtitles, 1):
            f.write(f"{i}\n")
            f.write(f"{format_time(subtitle['start_time'])} --> {format_time(subtitle['end_time'])}\n")
            f.write(f"{subtitle['text']}\n\n")
    
    return output_path