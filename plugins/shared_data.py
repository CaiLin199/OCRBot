import logging

# Configure logging
logger = logging.getLogger(__name__)

# Shared user data dictionary
user_data = {}

# Mode constants
AUTO_MODE = "auto"
MANUAL_MODE = "manual"

async def progress_bar(current, total, message, start_time=None, operation=None, username=None):
    """Progress bar that accepts extra parameters but maintains simple functionality"""
    try:
        percent = (current * 100 / total) if total > 0 else 0
        current_mb = current / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        
        status = f"Processing: {percent:.1f}%\n{current_mb:.1f} MB / {total_mb:.1f} MB"
        await message.edit(status)
            
    except Exception as e:
        logger.error(f"Progress update failed: {str(e)}")

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