import logging
import asyncio
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Store the last update time
last_update_time = {}

class StatusMessages:
    def __init__(self, pm_message, channel_message):
        self.pm = pm_message
        self.channel = channel_message

async def progress_bar(current, total, messages: StatusMessages, start_time, action="Processing"):
    """
    Enhanced progress bar with different formats for PM and channel
    Using same width characters for filled/unfilled (■/□)
    6 second delay between updates to avoid flood wait
    """
    try:
        now = datetime.now()
        msg_id = f"{messages.pm.chat.id}_{messages.pm.id}"
        last_time = last_update_time.get(msg_id, 0)
        
        # Update only every 6 seconds to avoid flood wait
        if (now.timestamp() - last_time) < 6:
            return
            
        diff = (now - start_time).total_seconds()
        if diff == 0:
            return
            
        # Calculate metrics
        speed = current / diff
        progress_percent = current * 100 / total
        eta = (total - current) / speed if speed > 0 else 0
        
        # Progress bar visualization with consistent width characters
        bar_length = 20
        filled_length = int(bar_length * current // total)
        bar = "■" * filled_length + "□" * (bar_length - filled_length)
        
        # Size calculations
        current_mb = current / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        speed_mb = speed / (1024 * 1024)
        
        # Channel message format
        channel_text = (
            f"🎬 {action}\n\n"
            f"📊 Progress Bar:\n"
            f"[{bar}]\n"
            f"▫️ Complete: {progress_percent:.1f}%\n"
            f"▫️ Speed: {speed_mb:.1f} MB/s\n"
            f"▫️ Size: {current_mb:.1f}MB / {total_mb:.1f}MB\n"
            f"▫️ ETA: {eta:.1f}s\n\n"
            f"⌚ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
        
        # PM message format
        pm_text = (
            f"⌚ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            f"🔄 {action}...\n\n"
            f"[{bar}] {progress_percent:.1f}%\n"
            f"💾 Size: {current_mb:.1f}MB / {total_mb:.1f}MB\n"
            f"⚡ Speed: {speed_mb:.1f} MB/s\n"
            f"⏱ ETA: {eta:.1f}s"
        )
        
        # Update messages
        try:
            await messages.pm.edit_text(pm_text)
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"PM update failed: {e}")
        
        try:
            await messages.channel.edit_text(channel_text)
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Channel update failed: {e}")
        
        last_update_time[msg_id] = now.timestamp()
        
    except Exception as e:
        logger.error(f"Progress update failed: {e}")

async def update_status_text(messages: StatusMessages, action: str):
    """
    Update status text without progress bar
    """
    channel_text = (
        f"🎬 {action}\n\n"
        f"⌚ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        "▫️ Status: Processing..."
    )
    
    pm_text = (
        f"⌚ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        f"🔄 {action}..."
    )
    
    try:
        await messages.pm.edit_text(pm_text)
        await messages.channel.edit_text(channel_text)
    except Exception as e:
        logger.error(f"Status update failed: {e}")

async def create_status_messages(client, user_message, channel_id):
    """
    Create initial status messages
    """
    try:
        initial_text = (
            "🎬 Initializing Process...\n\n"
            f"⌚ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            "▫️ Status: Starting..."
        )
        
        pm_msg = await user_message.reply(initial_text)
        channel_msg = await client.send_message(channel_id, initial_text)
        return StatusMessages(pm_msg, channel_msg)
    except Exception as e:
        logger.error(f"Failed to create status messages: {e}")
        return None

def create_progress_callback(messages: StatusMessages, start_time, action):
    """
    Create progress callback for file operations
    """
    loop = asyncio.get_event_loop()
    
    def callback(current, total):
        return asyncio.run_coroutine_threadsafe(
            progress_bar(current, total, messages, start_time, action),
            loop
        )
    
    return callback

async def delete_channel_status(message):
    """
    Delete channel status message
    """
    try:
        if message:
            await message.delete()
    except Exception as e:
        logger.error(f"Failed to delete channel message: {e}")