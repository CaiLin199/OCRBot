import asyncio
import feedparser
from database.database import database  # Ensure you import the database class
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Import configuration variables
from config import TELEGRAM_TOKEN, CHANNEL_IDS, RSS_URL, API_HASH, API_ID, ADMINS

# Import your custom Bot class
from bot import Bot  # Import your custom Bot class

# Global variables to control fetching state and task
is_fetching = False
fetch_task = None  # Stores the fetch task so it can be canceled

async def fetch_and_send_news(client: Client):  # Pass the client instance
    global is_fetching

    while is_fetching:
        feed = feedparser.parse(RSS_URL)

        new_entries_found = False  # Track if new entries are found

        for entry in feed.entries:
            if not is_fetching:  # Check if fetching is stopped
                break

            title = entry.title
            link = entry.link

            # Check for duplicates using the link
            if database.check_duplicate(link):
                print(f"Duplicate news found: {link}. Skipping...")
                continue  # Skip sending this news

            # Get the thumbnail image URL
            image_url = get_thumbnail_url(entry)

            # Prepare the message
            caption = f"{title}\n\n💫🌵 - @Anime_NewsPixelify"

            for channel_id in CHANNEL_IDS:  # Iterate through all channel IDs
                if image_url:
                    print(f"Sending photo to {channel_id}: {image_url}")
                    try:
                        await client.send_photo(chat_id=channel_id, photo=image_url, caption=caption)
                    except Exception as e:
                        print(f"Failed to send photo to {channel_id}: {e}")
                else:
                    print(f"No valid image URL found, sending message only to {channel_id}.")
                    try:
                        await client.send_message(chat_id=channel_id, text=caption)
                    except Exception as e:
                        print(f"Failed to send message to {channel_id}: {e}")

            # Insert the new news link into the database
            database.insert_news(link)

            # Indicate that a new entry was found and sent
            new_entries_found = True

            # Delay between messages to avoid flooding
            await asyncio.sleep(5)

        # If no new entries are found, wait before the next check
        if not new_entries_found:
            print("No new entries. Waiting to check again...")
            await asyncio.sleep(60)  # Wait for 60 seconds before checking again

def get_thumbnail_url(entry):
    if hasattr(entry, 'media_thumbnail'):
        return entry.media_thumbnail[0]['url']
    return None

@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command('animenewson'))
async def start_fetching(client: Client, message):
    global is_fetching, fetch_task

    if not is_fetching:
        is_fetching = True
        await message.reply_text("Fetching anime news started!")
        fetch_task = asyncio.create_task(fetch_and_send_news(client))  # Store the fetch task
    else:
        await message.reply_text("Already fetching anime news.")

@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command('animenewsoff'))
async def stop_fetching(client: Client, message):
    global is_fetching, fetch_task

    if is_fetching:
        is_fetching = False
        if fetch_task:
            fetch_task.cancel()  # Cancel the running fetch task
            fetch_task = None  # Reset the task variable
        await message.reply_text("Fetching anime news stopped.")
    else:
        await message.reply_text("Not currently fetching anime news.")