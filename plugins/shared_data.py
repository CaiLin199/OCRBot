import logging
import time
import asyncio
from typing import Dict, Any

# Configure logging
logger = logging.getLogger(__name__)

# Shared data storage
user_data: Dict[str, Dict[str, Any]] = {}

# Progress tracking
class ProgressTracker:
    def __init__(self):
        self.last_update = 0
        self.last_current = 0
        self.start_time = time.time()
        self.previous_text = ""

_progress_trackers: Dict[str, ProgressTracker] = {}
PROGRESS_BAR_LENGTH = 10
UPDATE_INTERVAL = 7.0  # 7 seconds to avoid flood wait

async def progress_bar(current: int, total: int, message: Any, type_message: str = "") -> None:
    """Progress bar with flood protection"""
    try:
        if not message or not hasattr(message, 'chat'):
            return

        now = time.time()
        msg_id = f"{message.chat.id}_{message.id}"
        
        if msg_id not in _progress_trackers:
            _progress_trackers[msg_id] = ProgressTracker()
        
        tracker = _progress_trackers[msg_id]
        
        if now - tracker.last_update < UPDATE_INTERVAL:
            return

        # Calculate progress
        percent = (current * 100 / total) if total > 0 else 0
        current_mb = current / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        
        # Progress bar
        done = int(PROGRESS_BAR_LENGTH * current / total) if total > 0 else 0
        progress_bar = '■' * done + '□' * (PROGRESS_BAR_LENGTH - done)
        
        # Status message
        status = (
            f'{type_message}...\n'
            f'[{progress_bar}] {percent:.1f}%\n'
            f'📦 Size: {current_mb:.1f}MB / {total_mb:.1f}MB'
        )
        
        if status != tracker.previous_text:
            await message.edit(status)
            tracker.previous_text = status
        
        tracker.last_update = now
        tracker.last_current = current
        
    except Exception as e:
        logger.info(f"Progress update: {str(e)}")

# Mode settings
AUTO_MODE = "auto"
MANUAL_MODE = "manual"

def get_current_mode() -> str:
    """Get current mode"""
    return user_data.get("global_mode", AUTO_MODE)

def is_auto_mode() -> bool:
    """Check if in auto mode"""
    return get_current_mode() == AUTO_MODE

def switch_mode() -> str:
    """Switch between modes"""
    current_mode = get_current_mode()
    new_mode = MANUAL_MODE if current_mode == AUTO_MODE else AUTO_MODE
    user_data["global_mode"] = new_mode
    return new_mode

def cleanup_user_data(user_id: str) -> None:
    """Clean up user data"""
    if user_id in user_data:
        del user_data[user_id]

async def create_progress_callback(message: Any, type_message: str = ""):
    """Create progress callback"""
    async def callback(current: int, total: int) -> None:
        await progress_bar(current, total, message, type_message)
    return callback