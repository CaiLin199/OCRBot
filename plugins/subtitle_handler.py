import os
import subprocess
import logging
from pyrogram import filters
from asyncio import create_task
from bot import Bot
from config import OWNER_IDS
from .video_handler import user_data, logger
from .ffmpeg_utils import merge_subtitles_task

@Bot.on_message(filters.user(OWNER_IDS) & filters.command("final"), group=0)
async def start_conversion(client, message):
    await message.reply("Send me the subtitle file (.srt or .vtt) for conversion.")

@Bot.on_message(
    filters.user(OWNER_IDS) &
    filters.document & filters.create(lambda _, __, m: m.document and m.document.file_name.endswith((".srt", ".vtt")))
)
async def handle_subtitle_conversion(client, message):
    user_id = message.from_user.id
    subtitle_file = await message.download()

    logger.info(f"Subtitle downloaded: {subtitle_file}")

    # Convert SRT and VTT to ASS
    ass_file = subtitle_file.rsplit('.', 1)[0] + ".ass"
    ffmpeg_cmd = ["ffmpeg", "-i", subtitle_file, ass_file]
    subprocess.run(ffmpeg_cmd, check=True)
    os.remove(subtitle_file)  # Remove original SRT or VTT file

    # Modify the .ass file
    with open(ass_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    modified_lines = []
    for line in lines:
        if line.startswith("Style: Default"):
            line = line.replace("Arial", "Oath-Bold").replace(",16,", ",20,")
        if line.startswith("Dialogue:"):
            parts = line.split(",", 9)  # Ensure the dialogue part is modified
            if len(parts) > 9:
                parts[9] = f"{{\\pos(193,265)}}{parts[9]}"
            line = ",".join(parts)
        modified_lines.append(line)

    with open(ass_file, "w", encoding="utf-8") as f:
        f.writelines(modified_lines)

    logger.info(f"Modified subtitle file: {ass_file}")

    # Send the modified subtitle file to the user
    await message.reply_document(document=ass_file, caption="Here is the converted and modified subtitle file.")

@Bot.on_message(
    filters.user(OWNER_IDS) &
    filters.document & filters.create(lambda _, __, m: m.document and m.document.file_name.endswith(".ass"))
)
async def handle_subtitle(client, message):
    user_id = message.from_user.id
    subtitle_file = await message.download()

    logger.info(f"Subtitle downloaded: {subtitle_file}")

    if user_id not in user_data:
        user_data[user_id] = {}

    user_data[user_id]["subtitle"] = subtitle_file
    user_data[user_id]["step"] = "subtitle"
    await message.reply("Subtitle received! Now send the new name for the output file (without extension).")

@Bot.on_message(filters.user(OWNER_IDS) & filters.text)
async def handle_name_or_caption(client, message):
    user_id = message.from_user.id

    logger.info(f"Receiving new filename from {user_id}")

    if user_id in user_data and user_data[user_id].get("step") == "subtitle":
        new_name = message.text.strip()

        user_data[user_id]["new_name"] = new_name
        user_data[user_id]["caption"] = new_name
        user_data[user_id]["step"] = "name"
        await message.reply("New name and caption received! Now processing the video.")
        create_task(merge_subtitles_task(client, message, user_id))
    else:
        await message.reply("Please start by sending a video file.")
