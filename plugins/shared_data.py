import logging

# Configure logging
logger = logging.getLogger(__name__)

# Shared user data dictionary
user_data = {}

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