import feedparser
import asyncio
import logging
from bot import Bot
from pyrogram import Client, filters
from config import OWNER_ID, DB_URI, DB_NAME, RSS_URL, CHECK_INTERVAL, CHANNEL_ID
from motor.motor_asyncio import AsyncIOMotorClient

# MongoDB Setup
mongo_client = AsyncIOMotorClient(DB_URI)
db = mongo_client[DB_NAME]
posts_collection = db.RSS_SENDED

# Logger setup
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Variables
rss_event = asyncio.Event()

async def fetch_and_send_rss(client: Client):
    logger.info("Starting RSS feed monitoring...")
    while rss_event.is_set():
        try:
            logger.info("Fetching RSS feed from %s", RSS_URL)
            feed = feedparser.parse(RSS_URL)
            if feed.entries:
                new_entries = []

                # Process entries in reverse (oldest to newest)
                for entry in reversed(feed.entries):
                    if not await posts_collection.find_one({"_id": entry.id}):
                        if not hasattr(entry, "id") or not entry.id:
                            logger.warning("Entry missing ID, skipping: %s", entry.title)
                            continue
                        new_entries.append(entry)

                if new_entries:
                    logger.info("Found %d new entries to process.", len(new_entries))

                for entry in new_entries:
                    title = entry.title
                    torrent_link = entry.link
                    message = f"> {title}\n\n{torrent_link}"

                    try:
                        await client.send_message(chat_id=CHANNEL_ID, text=message)
                        logger.info("Successfully sent post: %s", title)
                        await posts_collection.insert_one({"_id": entry.id, "title": title, "link": torrent_link})

                        # Wait for 10 seconds before processing the next entry
                        await asyncio.sleep(10)
                    except Exception as e:
                        logger.error("Failed to send post: %s. Error: %s", title, str(e))
                else:
                    logger.info("No new entries to process.")
            else:
                logger.warning("No entries found in the RSS feed.")
        except Exception as e:
            logger.error("Error while fetching RSS feed: %s", str(e))

        await asyncio.sleep(CHECK_INTERVAL)

    logger.info("RSS feed monitoring stopped.")


# Start command
@Bot.on_message(filters.command("start") & filters.user(OWNER_ID))
async def start_rss(client: Client, message):
    if not rss_event.is_set():
        rss_event.set()
        logger.info("Start command received. Starting RSS monitoring.")
        await message.reply_text("✅ RSS feed monitoring started.")
        asyncio.create_task(fetch_and_send_rss(client))
    else:
        logger.info("Start command received, but monitoring is already running.")
        await message.reply_text("⚠️ RSS feed monitoring is already running.")

# Stop command
@Bot.on_message(filters.command("stop") & filters.user(OWNER_ID))
async def stop_rss(client: Client, message):
    if rss_event.is_set():
        rss_event.clear()
        logger.info("Stop command received. Stopping RSS monitoring.")
        await message.reply_text("✅ RSS feed monitoring stopped.")
    else:
        logger.info("Stop command received, but monitoring is not running.")
        await message.reply_text("⚠️ RSS feed monitoring is not running.")