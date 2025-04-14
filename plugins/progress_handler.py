import logging
import asyncio
import time
from datetime import datetime
from typing import Optional

# Configure logging
logger = logging.getLogger(__name__)

class StatusMessages:
    def __init__(self, pm_message, channel_message):
        self.pm = pm_message
        self.channel = channel_message
        self.msg_id = f"{pm_message.chat.id}_{pm_message.id}" if pm_message else None
        self.last_update = 0

async def progress_bar(current: int, total: int, messages: StatusMessages, start_time: datetime, action: str = "Processing") -> None:
    """Simple progress bar with PM and channel updates"""
    try:
        if not messages or not messages.msg_id:
            return

        now = time.time()
        
        # Update only every 7 seconds to avoid flood wait
        if (now - messages.last_update) < 7:
            return
            
        # Calculate basic metrics
        progress_percent = (current * 100 / total) if total > 0 else 0
        current_mb = current / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        
        # Create simple progress bar
        bar_length = 10
        filled_length = int(bar_length * current // total) if total > 0 else 0
        bar = "■" * filled_length + "□" * (bar_length - filled_length)
        
        # Simple PM message
        pm_text = (
            f"🔄 {action}\n"
            f"[{bar}] {progress_percent:.1f}%\n"
            f"💾 {current_mb:.1f}/{total_mb:.1f} MB"
        )
        
        # Simple channel message
        channel_text = (
            f"🎬 {action}\n"
            f"[{bar}] {progress_percent:.1f}%\n"
            f"📊 {current_mb:.1f}/{total_mb:.1f} MB"
        )
        
        # Update messages
        try:
            if messages.pm:
                await messages.pm.edit_text(pm_text)
            if messages.channel:
                await messages.channel.edit_text(channel_text)
            messages.last_update = now
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.info(f"Message edit: {str(e)}")
        
    except Exception as e:
        logger.info(f"Progress update: {str(e)}")

async def create_status_messages(client, user_message, channel_id: Optional[int] = None) -> Optional[StatusMessages]:
    """Create initial status messages"""
    try:
        pm_msg = await user_message.reply("🎬 Starting...")
        channel_msg = await client.send_message(channel_id, "🎬 Starting...") if channel_id else None
        return StatusMessages(pm_msg, channel_msg)
    except Exception as e:
        logger.info(f"Status message creation: {str(e)}")
        return None

def create_progress_callback(messages: StatusMessages, start_time: datetime, action: str):
    """Simple progress callback creator"""
    async def callback(current: int, total: int) -> None:
        await progress_bar(current, total, messages, start_time, action)
    return callback

async def update_status(messages: StatusMessages, text: str) -> None:
    """Update status text"""
    if not messages:
        return
    try:
        if messages.pm:
            await messages.pm.edit_text(text)
        if messages.channel:
            await messages.channel.edit_text(text)
    except Exception as e:
        logger.info(f"Status update: {str(e)}")

async def cleanup_messages(messages: StatusMessages) -> None:
    """Clean up messages"""
    if not messages:
        return
    try:
        if messages.pm:
            await messages.pm.delete()
        if messages.channel:
            await messages.channel.delete()
    except Exception:
        pass