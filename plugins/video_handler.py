import os
import asyncio
from pyrogram import filters
from bot import Bot
from config import OWNER_ID, MAIN_CHANNEL
from datetime import datetime
from .shared_data import logger
from .post_handler import PostHandler
from .upload_handler import UploadHandler
from .progress import Progress
from .aria2_client import aria2

# Initialize handlers
post_handler = PostHandler()

class VideoHandler:
    def __init__(self):
        self.bot = Bot()
        logger.info("VideoHandler initialized")

    async def _handle_ddl(self, client, message):
        """Handle DDL command and process downloads"""
        try:
            # Rest of your _handle_ddl code remains the same
            ...

# Create handler instance
video_handler = VideoHandler()

# Move command handlers outside the class
@Bot.on_message(filters.command('ddl') & filters.user(OWNER_ID))
async def handle_ddl(client, message):
    await video_handler._handle_ddl(client, message)

@Bot.on_message(filters.command('post') & filters.user(OWNER_ID))
async def handle_post(client, message):
    await post_handler.handle_post_command(client, message)

@Bot.on_callback_query()
async def handle_callbacks(client, callback_query):
    try:
        if callback_query.data == "create_post":
            success, custom_msg = await post_handler.handle_callback(client, callback_query)
            if success:
                await video_handler._handle_ddl(client, custom_msg)
        else:
            await post_handler.handle_callback(client, callback_query)
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await callback_query.answer("An error occurred", show_alert=True)

@Bot.on_message(filters.private & filters.user(OWNER_ID))
async def handle_post_input(client, message):
    await post_handler.handle_input(client, message)

# Add a test command to verify bot is working
@Bot.on_message(filters.command('ping'))
async def ping_command(client, message):
    try:
        await message.reply("Pong! Bot is working!")
        logger.info("Ping command successful")
    except Exception as e:
        logger.error(f"Ping error: {e}")