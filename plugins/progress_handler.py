import logging
import asyncio
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Store the last update time
last_update_time = {}

async def update_status(status_msg, text, channel_message=None):
    """
    Updates status message in both PM and channel if exists
    """
    try:
        await status_msg.edit_text(text)
        if hasattr(status_msg, 'channel_message') and status_msg.channel_message:
            await status_msg.channel_message.edit_text(text)
    except Exception as e:
        logger.error(f"Failed to update status: {e}")

async def progress_bar(current, total, status_msg, start_time, action="Processing", user_login=None):
    """
    Enhanced progress bar for Telegram file operations with timestamp, user info, speed and ETA
    Fixed width progress bar to prevent line wrapping
    """
    try:
        # Get the current time
        now = datetime.now()
        
        # Get the last update time for this message
        msg_id = f"{status_msg.chat.id}_{status_msg.id}"
        last_time = last_update_time.get(msg_id, 0)
        
        # Check if enough time has passed since the last update (7 seconds)
        if (now.timestamp() - last_time) < 7:
            return
            
        diff = (now - start_time).total_seconds()
        
        if diff == 0:
            return
            
        speed = current / diff
        progress_percent = current * 100 / total
        eta = (total - current) / speed if speed > 0 else 0
        
        # Fixed width progress bar (15 characters to prevent wrapping)
        bar_length = 8
        filled_length = int(bar_length * current // total)
        bar = "█" * filled_length + "-" * (bar_length - filled_length)
        
        # Calculate sizes in MB
        current_mb = current / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        speed_mb = speed / (1024 * 1024)
        
        # Get current UTC time
        current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        
        # Fixed width format to prevent line wrapping
        progress_text = (
            f"⌚ Time: {current_time} UTC\n"
            f"👤 User: {user_login}\n"
            f"🔄 {action}...\n"
            f"[{bar}] {progress_percent:5.1f}%\n"  # Fixed width percentage
            f"💾 Size: {current_mb:7.1f}MB / {total_mb:7.1f}MB\n"  # Fixed width sizes
            f"⚡ Speed: {speed_mb:7.1f} MB/s\n"  # Fixed width speed
            f"⏱ ETA: {eta:5.1f}s"  # Fixed width ETA
        )
        
        # Update in PM and channel
        await update_status(status_msg, progress_text)
        
        # Update the last update time
        last_update_time[msg_id] = now.timestamp()
        
        # Cleanup old messages periodically
        if len(last_update_time) > 100:  # Arbitrary threshold
            cleanup_old_messages()
            
    except Exception as e:
        logger.error(f"Failed to update progress bar: {e}")
        try:
            if str(e).find("FLOOD_WAIT") == -1:  # Only show error if it's not a flood wait
                await update_status(status_msg, f"Error during {action.lower()} progress: {e}")
        except:
            pass

def create_progress_callback(status_msg, start_time, action, user_login):
    """
    Creates a progress callback function for use with asyncio.run_coroutine_threadsafe
    """
    loop = asyncio.get_event_loop()
    
    def callback(current, total):
        return asyncio.run_coroutine_threadsafe(
            progress_bar(current, total, status_msg, start_time, action=action, user_login=user_login),
            loop
        )
    
    return callback

def cleanup_old_messages():
    """
    Remove old message timestamps to prevent memory leaks
    """
    current_time = datetime.now().timestamp()
    to_remove = []
    for msg_id, last_time in last_update_time.items():
        if (current_time - last_time) > 3600:  # Remove entries older than 1 hour
            to_remove.append(msg_id)
    for msg_id in to_remove:
        last_update_time.pop(msg_id, None)