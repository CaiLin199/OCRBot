import logging
from pyrogram import filters
from bot import Bot
from config import OWNER_IDS
from .video_handler import user_data

# Configure logging
logger = logging.getLogger(__name__)

# Mode constants
AUTO_MODE = "auto"  # Default mode
MANUAL_MODE = "manual"

def get_current_mode():
    """
    Get the current mode. Always defaults to AUTO_MODE if not set.
    This is a global setting, not per user.
    """
    return user_data.get("global_mode", AUTO_MODE)

def is_auto_mode():
    """Check if currently in auto mode"""
    return get_current_mode() == AUTO_MODE

@Bot.on_message(filters.user(OWNER_IDS) & filters.command("mode"))
async def switch_mode(client, message):
    """Switch between auto and manual processing modes (owner only)"""
    try:
        # Get current global mode
        current_mode = get_current_mode()
        
        # Switch mode
        new_mode = MANUAL_MODE if current_mode == AUTO_MODE else AUTO_MODE
        
        # Update global mode
        user_data["global_mode"] = new_mode
        
        # Send confirmation message
        await message.reply(
            f"✅ Mode switched to: {new_mode.upper()}\n"
            f"{'🤖 Automatic subtitle processing enabled' if new_mode == AUTO_MODE else '👤 Manual subtitle processing enabled'}"
        )
        
        logger.info(f"Mode switched to {new_mode} by owner")
        
    except Exception as e:
        logger.error(f"Error in switch_mode: {e}")
        await message.reply("❌ Error switching modes. Please try again.")