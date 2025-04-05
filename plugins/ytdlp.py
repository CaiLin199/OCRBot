# plugins/ytdlp.py
import youtube_dl
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
from bot import Bot
import time


# Command to handle /ytdl
@Bot.on_message(filters.command(["ytdl"]))
async def ytdl(client, message):
    url = message.text.split(" ", 1)[1]
    ydl_opts = {
        'format': 'best',
        'noplaylist': True
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        formats = info_dict.get('formats', None)
        
        buttons = []
        for fmt in formats:
            if fmt.get('height') and fmt.get('width'):
                button_text = f"{fmt['height']}p"
                button_data = f"ytdl_{fmt['format_id']}_{url}"
                buttons.append([InlineKeyboardButton(button_text, callback_data=button_data)])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply("Choose the resolution:", reply_markup=reply_markup)

# Callback handler for resolution selection
@Bot.on_callback_query(filters.regex(r"^ytdl_"))
async def callback_query(client, callback_query):
    data = callback_query.data.split("_")
    format_id = data[1]
    url = data[2]

    ydl_opts = {
        'format': format_id,
        'progress_hooks': [lambda d: progress_hook(d, callback_query)],
        'noplaylist': True,
        'outtmpl': '%(title)s.%(ext)s'
    }

    await callback_query.message.edit_text("Downloading...")
    
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

last_update_time = 0

def progress_hook(d, callback_query):
    global last_update_time
    if d['status'] == 'downloading':
        downloaded = d['downloaded_bytes']
        total = d['total_bytes']
        percentage = downloaded / total * 100
        current_time = time.time()
        if current_time - last_update_time >= 3:
            last_update_time = current_time
            asyncio.create_task(update_progress_bar(callback_query, percentage))

async def update_progress_bar(callback_query, percentage):
    progress_bar = f"[{'=' * int(percentage // 10)}{' ' * (10 - int(percentage // 10))}] {percentage:.2f}%"
    await callback_query.message.edit_text(f"Downloading...\n{progress_bar}")