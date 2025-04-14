from pyrogram import filters
from bot import Bot
from .video_handler import user_data, logger
from .subtitle_utils import extract_subtitles
from .screenshot_utils import generate_screenshot

@Bot.on_callback_query(filters.regex(r"(merge|extract|screenshot)_(\d+)"))
async def handle_button_click(client, callback_query):
    action = callback_query.matches[0].group(1)
    user_id = int(callback_query.matches[0].group(2))

    if action == "merge":
        await callback_query.message.reply("Send the subtitle file (.ass) to merge.")
    elif action == "extract":
        await extract_subtitles(client, callback_query.message, user_id)
    elif action == "screenshot":
        await generate_screenshot(client, callback_query.message, user_id)