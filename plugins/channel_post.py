# donot use this codes

'''
import logging
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
import re
from config import MAIN_CHANNEL, ANIME_COVER, STICKER_ID

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def extract_episode_number(filename):
    """Extract episode number from filename."""
    try:
        # First try to match [number] format
        match = re.search(r'\[(\d+)\]', filename)
        if match:
            return int(match.group(1))
            
        # Fallback to original format
        match = re.search(r'(?:Episode\s*)?(\d+)', filename)
        if match:
            return int(match.group(1))
            
        logger.warning(f"No episode number found in filename: {filename}")
        return None
    except Exception as e:
        logger.error(f"Failed to extract episode number: {e}")
        return None

async def post_to_main_channel(client, episode_info, share_link):
    """
    Post anime episode to main channel with formatted message.
    
    Args:
        client: Pyrogram client instance
        episode_info: filename containing episode number
        share_link: Generated share link for the episode
    """
    try:
        episode_number = extract_episode_number(episode_info)
        if not episode_number:
            logger.error("No episode number found")
            return False

        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("• ᴅᴏᴡɴʟᴏᴀᴅ / ᴡᴀᴛᴄʜ •", url=share_link)]
        ])

        post_text = (
            f"**☗   Battle Through The Heavens**\n\n"
            f"**⦿   Ratings: 9.8**\n"
            f"**⦿   Status: Airing**\n"
            f"**⦿   Episode: {episode_number}**\n"
            f"**⦿   Quality: 720p**\n"
            f"**⦿   Genres: `Action`, `Adventure`, `Harem`, `Romance`, `Cultivation`**\n\n"
            f"**◆   Synopsis: __In a land where no magic is present. A land where the strong make the rules and weak have to obey...[Read More](https://myanimelist.net/anime/36491/Doupo_Cangqiong)__**\n"
        )

        # Send main post with photo
        await client.send_photo(
            chat_id=MAIN_CHANNEL,
            photo=ANIME_COVER,
            caption=post_text,
            reply_markup=button,
            parse_mode=ParseMode.MARKDOWN
        )

        # Send sticker
        await client.send_sticker(
            chat_id=MAIN_CHANNEL,
            sticker=STICKER_ID
        )

        logger.info(f"Successfully posted episode {episode_number} to main channel")
        return True

    except Exception as e:
        logger.error(f"Failed to post to main channel: {e}")
        return False

        '''
