import os
import subprocess
import logging
from pyrogram import filters
from bot import Bot
from config import OWNER_ID

@Bot.on_message(filters.user(OWNER_ID) & filters.command("final"), group=0)
async def start_conversion(client, message):
    await message.reply("Send me the subtitle file (.srt or .vtt) for conversion.")

# Subtitle Upload Handler
@Bot.on_message(
    filters.user(OWNER_ID) &
    filters.document & filters.create(lambda _, __, m: m.document and m.document.file_name.endswith((".srt", ".vtt")))
)
async def handle_subtitle_conversion(client, message):
    user_id = message.from_user.id
    subtitle_file = await message.download()

    logging.info(f"Subtitle downloaded: {subtitle_file}")

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

    logging.info(f"Modified subtitle file: {ass_file}")

    # Send the modified subtitle file to the user
    await message.reply_document(document=ass_file, caption="Here is the converted and modified subtitle file.")