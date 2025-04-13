import os
import logging
from pyrogram import filters
from bot import Bot
from config import OWNER_IDS
from .video_handler import user_data
from .ffmpeg_utils import merge_subtitles_task

@Bot.on_message(
    filters.user(OWNER_IDS) &
    filters.document & filters.create(lambda _, __, m: m.document and m.document.file_name.endswith((".srt", ".vtt", ".ass")))
)
async def handle_subtitle_conversion(client, message):
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

    if user_id in user_data and user_data[user_id].get("step") == "subtitle":
        new_name = message.text.strip()

        user_data[user_id]["new_name"] = new_name
        user_data[user_id]["caption"] = new_name
        user_data[user_id]["step"] = "name"
        await message.reply("New name and caption received! Now processing the video.")
        create_task(merge_subtitles_task(client, message, user_id))
    else:
        await message.reply("Please start by sending a video file.")