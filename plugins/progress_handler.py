import logging
import asyncio
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

async def progress_bar(current, total, status_msg, start_time, action="Processing", user_login=None):
    """
    Enhanced progress bar for Telegram file operations with timestamp, user info, speed and ETA
    """
    try:
        now = datetime.now()
        diff = (now - start_time).total_seconds()
        
        if diff == 0:
            return
            
        speed = current / diff
        progress_percent = current * 100 / total
        eta = (total - current) / speed if speed > 0 else 0
        
        bar_length = 20
        filled_length = int(bar_length * current // total)
        bar = "█" * filled_length + "-" * (bar_length - filled_length)
        
        # Calculate sizes in MB
        current_mb = current / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        speed_mb = speed / (1024 * 1024)
        
        # Get current UTC time
        current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        
        # Create progress text with timestamp and user info
        progress_text = (
            f"⌚ Time: {current_time} UTC\n"
            f"👤 User: {user_login}\n"
            f"🔄 {action}...\n"
            f"[{bar}] {progress_percent:.2f}%\n"
            f"💾 Size: {current_mb:.2f}MB / {total_mb:.2f}MB\n"
            f"⚡ Speed: {speed_mb:.2f} MB/s\n"
            f"⏱ ETA: {eta:.1f}s"
        )
        
        await status_msg.edit_text(progress_text)
    except Exception as e:
        logger.error(f"Failed to update progress bar: {e}")
        try:
            await status_msg.edit_text(f"Error during {action.lower()} progress: {e}")
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