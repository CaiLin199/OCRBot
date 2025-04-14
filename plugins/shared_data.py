import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Shared user data dictionary
user_data = {}

# Progress bar settings
PROGRESS_BAR_LENGTH = 10  # Length of the progress bar

async def progress_bar(current, total, message, type_message=""):
    """
    Progress bar with basic error handling and consistent format.
    Args:
        current (int): Current progress
        total (int): Total size
        message (Message): Message object to edit
        type_message (str): Type of operation (e.g., "Downloading", "Uploading")
    """
    try:
        percent = float(current) * 100 / float(total)
        current_mb = current / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        speed = current_mb / 100  # Simplified speed calculation
        
        # Create progress bar using ■ and □
        done = int(percent / (100 / PROGRESS_BAR_LENGTH))
        progress_bar = ('■' * done + '□' * (PROGRESS_BAR_LENGTH - done))
        
        # Format message
        status = f'{type_message}...\n'
        status += f'[{progress_bar}] {percent:.1f}%\n'
        status += f'Size: {current_mb:.1f}MB / {total_mb:.1f}MB\n'
        status += f'Speed: {speed:.1f} MB/s'
        
        await message.edit(status)
    except Exception as e:
        logger.error(f"Progress update failed: {e}")

# Mode constants
AUTO_MODE = "auto"
MANUAL_MODE = "manual"

def get_current_mode():
    """Get the current mode. Always defaults to AUTO_MODE if not set"""
    return user_data.get("global_mode", AUTO_MODE)

def is_auto_mode():
    """Check if currently in auto mode"""
    return get_current_mode() == AUTO_MODE

def switch_mode():
    """Switch between auto and manual modes"""
    current_mode = get_current_mode()
    new_mode = MANUAL_MODE if current_mode == AUTO_MODE else AUTO_MODE
    user_data["global_mode"] = new_mode
    logger.info(f"Mode switched to {new_mode}")
    return new_mode

# Reset user data
def cleanup_user_data(user_id):
    """Clean up user data for a specific user"""
    if user_id in user_data:
        del user_data[user_id]
        logger.info(f"Cleaned up data for user {user_id}")

# Progress update locks
progress_locks = {}

def get_progress_lock(user_id):
    """Get or create a progress lock for a user"""
    if user_id not in progress_locks:
        from asyncio import Lock
        progress_locks[user_id] = Lock()
    return progress_locks[user_id]

def cleanup_progress_lock(user_id):
    """Clean up progress lock for a specific user"""
    if user_id in progress_locks:
        del progress_locks[user_id]
        logger.info(f"Cleaned up progress lock for user {user_id}")