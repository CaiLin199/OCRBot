# main file to handler all callbacks and commands

from bot import Bot
from config import OWNER_ID, CHANNEL_ID, MAIN_CHANNEL
from pyrogram import filters

@Bot.on_message(filters.private & filters.command("post") & filters.user(OWNER_ID))
async def post_command(client, message):
    