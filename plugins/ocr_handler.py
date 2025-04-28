import os
import asyncio
import subprocess
import shutil
import easyocr
from pyrogram import Client, filters
from pyrogram.types import Message
from logging import getLogger
from glob import glob
from bot import Bot
from config import LOGGER

# OCR Reader Setup
reader = easyocr.Reader(['ch_sim'], gpu=False)  # Chinese Simplified, CPU only

# Frame Extraction Rate
FRAME_RATE = 5  # frames per second

@Bot.on_message(filters.video | filters.document)
async def extract_hardsub(_, message: Message):
    # Download the video
    video_path = await message.download(file_name="video.mp4")
    LOGGER.info(f"Downloaded: {video_path}")

    # Prepare frames folder
    if os.path.exists("frames"):
        shutil.rmtree("frames")
    os.makedirs("frames", exist_ok=True)

    # Extract frames
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"fps={FRAME_RATE}",
        "frames/frame_%05d.jpg"
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    LOGGER.info("Frames extracted.")

    frames = sorted(glob("frames/*.jpg"))
    subtitles = []
    last_text = ""
    start_time = None

    for idx, frame_path in enumerate(frames):
        timestamp = idx / FRAME_RATE  # seconds
        result = reader.readtext(frame_path, detail=0)
        text = " ".join(result).strip()

        if text != last_text:
            if last_text and last_text.strip() != "":
                subtitles.append((start_time, timestamp, last_text))
            start_time = timestamp
            last_text = text

        # Remove frame immediately to save RAM
        os.remove(frame_path)

    # Save last subtitle
    if last_text and last_text.strip() != "":
        subtitles.append((start_time, (len(frames) / FRAME_RATE), last_text))

    # Create SRT
    srt_content = create_srt(subtitles)

    with open("subtitles.srt", "w", encoding="utf-8") as f:
        f.write(srt_content)

    await message.reply_document("subtitles.srt")
    LOGGER.info("SRT sent.")

    # Cleanup
    os.remove(video_path)
    os.remove("subtitles.srt")
    shutil.rmtree("frames")
    LOGGER.info("Cleanup done.")

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