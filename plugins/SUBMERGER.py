from pyrogram import Client, filters
import os
import subprocess
from bot import Bot

# Temporary storage for user file paths
user_data = {}

@Bot.on_message(filters.video | filters.document & filters.create(lambda _, __, message: message.document and message.document.file_name.endswith((".mkv", ".mp4"))))
async def handle_video(client, message):
    video_file = await message.download()
    user_id = message.from_user.id

    # Store the video file path
    user_data[user_id] = {"video": video_file}
    await message.reply("Video received! Please send the subtitle file (.ass or .srt).")

@Bot.on_message(filters.document & filters.create(lambda _, __, message: message.document and message.document.file_name.endswith((".ass", ".srt"))))
async def handle_subtitle(client, message):
    user_id = message.from_user.id
    if user_id in user_data and "video" in user_data:
        subtitle_file = await message.download()
        user_data[user_id]["subtitle"] = subtitle_file
        await message.reply("Subtitle received! Please send the font file (.ttf or .otf).")
    elif user_id in user_data:
        await message.reply("You need to send a video file first.")
    else:
        await message.reply("Please start by sending a video file.")

@Bot.on_message(filters.document & filters.create(lambda _, __, message: message.document and message.document.file_name.endswith((".ttf", ".otf"))))
async def handle_font(client, message):
    user_id = message.from_user.id
    if user_id in user_data and "subtitle" in user_data:
        font_file = await message.download()
        user_data[user_id]["font"] = font_file

        # All files are ready, start processing
        await message.reply("Font file received! Merging subtitles into the video...")
        await merge_subtitles(client, message, user_id)
    elif user_id in user_data:
        await message.reply("You need to send a subtitle file first.")
    else:
        await message.reply("Please start by sending a video file.")

async def merge_subtitles(client, message, user_id):
    data = user_data[user_id]
    video = data["video"]
    subtitle = data["subtitle"]
    font = data.get("font")
    output_file = f"output_{user_id}.mkv"

    ffmpeg_cmd = [
        "ffmpeg", "-i", video, "-i", subtitle,
        "-attach", font, "-metadata:s:t:0", "mimetype=application/x-font-otf",
        "-map", "0", "-map", "1",
        "-metadata:s:s:0", "title=HeavenlySubs",
        "-metadata:s:s:0", "language=eng", "-disposition:s:s:0", "default",
        "-c", "copy", output_file
    ]

    try:
        # Run ffmpeg
        subprocess.run(ffmpeg_cmd, check=True)
        await message.reply_video(video=output_file, caption="Here is your video with subtitles!")
    except subprocess.CalledProcessError as e:
        await message.reply(f"Failed to merge subtitles: {e}")
    finally:
        # Clean up
        os.remove(video)
        os.remove(subtitle)
        if font:
            os.remove(font)
        if os.path.exists(output_file):
            os.remove(output_file)
        user_data.pop(user_id, None)

@Bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply("Send me a video file (MKV or MP4) to start adding subtitles.")
