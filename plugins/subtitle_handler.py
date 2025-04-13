import os
import subprocess
import asyncio
from pyrogram import filters
from bot import Bot
from plugins.storage_handler import user_data
import logging

logger = logging.getLogger(__name__)

# Subtitle Upload Handler
@Bot.on_message(
    filters.user(OWNER_IDS) &
    filters.document & filters.create(lambda _, __, m: m.document and m.document.file_name.endswith((".srt", ".vtt")))
)
async def handle_subtitle_conversion(client, message):
    user_id = message.from_user.id
    try:
        status_msg = await message.reply("Preparing to download subtitle...")
        loop = asyncio.get_event_loop()
        subtitle_file = await message.download(
            file_name=f"sub_{user_id}.ass",
            progress=lambda current, total: asyncio.run_coroutine_threadsafe(
                progress_bar(current, total, status_msg, action="Downloading Subtitle"), loop
            )
        )
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
    except Exception as e:
        logger.error(f"Subtitle conversion failed: {e}")
        await message.reply(f"Error during subtitle conversion: {e}")