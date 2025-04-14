import logging
import time
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Configure logging
logger = logging.getLogger(__name__)

# Shared user data dictionary with proper typing
user_data: Dict[str, Dict[str, Any]] = {}

# Progress tracking
@dataclass
class ProgressTracker:
    last_update: float = 0
    last_current: int = 0
    start_time: float = 0
    previous_text: str = ""

_progress_trackers: Dict[str, ProgressTracker] = {}
PROGRESS_BAR_LENGTH = 10
UPDATE_INTERVAL = 7.0  # Update interval in seconds

async def progress_bar(current: int, total: int, message: Any, type_message: str = "") -> None:
    """
    Enhanced progress bar with proper error handling and rate limiting.
    Args:
        current (int): Current progress
        total (int): Total size
        message (Message): Message object to edit
        type_message (str): Type of operation (e.g., "Downloading", "Uploading")
    """
    try:
        if not message or not hasattr(message, 'chat'):
            return

        now = time.time()
        msg_id = f"{message.chat.id}_{message.id}"
        
        # Initialize progress tracker if not exists
        if msg_id not in _progress_trackers:
            _progress_trackers[msg_id] = ProgressTracker(
                start_time=now,
                last_update=0,
                last_current=0
            )
        
        tracker = _progress_trackers[msg_id]
        
        # Update only every UPDATE_INTERVAL seconds
        if now - tracker.last_update < UPDATE_INTERVAL:
            return

        # Calculate progress metrics
        percent = (current * 100 / total) if total > 0 else 0
        current_mb = current / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        
        # Calculate speed
        time_diff = now - tracker.last_update if tracker.last_update > 0 else 1
        current_diff = current - tracker.last_current
        speed_mb = (current_diff / time_diff) / (1024 * 1024) if time_diff > 0 else 0
        
        # Calculate ETA
        remaining_bytes = total - current
        eta_seconds = int(remaining_bytes / (current_diff / time_diff)) if current_diff > 0 and time_diff > 0 else 0
        
        # Create progress bar
        done = int(PROGRESS_BAR_LENGTH * current / total) if total > 0 else 0
        progress_bar = '■' * done + '□' * (PROGRESS_BAR_LENGTH - done)
        
        # Format status message
        status = (
            f'{type_message}...\n'
            f'[{progress_bar}] {percent:.1f}%\n'
            f'📦 Size: {current_mb:.1f}MB / {total_mb:.1f}MB\n'
            f'⚡ Speed: {speed_mb:.1f} MB/s\n'
            f'⏱ ETA: {eta_seconds}s'
        )
        
        # Only update if text has changed
        if status != tracker.previous_text:
            try:
                await asyncio.wait_for(message.edit(status), timeout=2.0)
                tracker.previous_text = status
            except asyncio.TimeoutError:
                logger.warning(f"Message edit timed out for {msg_id}")
            except Exception as e:
                if "message is not modified" not in str(e).lower():
                    logger.error(f"Failed to edit message: {e}")
        
        # Update tracker
        tracker.last_update = now
        tracker.last_current = current
        
    except Exception as e:
        logger.error(f"Progress update failed: {e}")
    finally:
        # Cleanup old trackers (older than 1 hour)
        cleanup_old_trackers()

def cleanup_old_trackers(max_age: int = 3600) -> None:
    """Clean up progress trackers older than max_age seconds"""
    now = time.time()
    for msg_id in list(_progress_trackers.keys()):
        tracker = _progress_trackers[msg_id]
        if now - tracker.start_time > max_age:
            del _progress_trackers[msg_id]

# Mode constants
AUTO_MODE = "auto"
MANUAL_MODE = "manual"

def get_current_mode() -> str:
    """Get the current mode. Always defaults to AUTO_MODE if not set"""
    return user_data.get("global_mode", AUTO_MODE)

def is_auto_mode() -> bool:
    """Check if currently in auto mode"""
    return get_current_mode() == AUTO_MODE

def switch_mode() -> str:
    """Switch between auto and manual modes"""
    current_mode = get_current_mode()
    new_mode = MANUAL_MODE if current_mode == AUTO_MODE else AUTO_MODE
    user_data["global_mode"] = new_mode
    logger.info(f"Mode switched to {new_mode}")
    return new_mode

def cleanup_user_data(user_id: str) -> None:
    """Clean up user data for a specific user"""
    if user_id in user_data:
        del user_data[user_id]
        logger.info(f"Cleaned up data for user {user_id}")

# Progress locks for thread safety
_progress_locks: Dict[str, asyncio.Lock] = {}

def get_progress_lock(user_id: str) -> asyncio.Lock:
    """Get or create a progress lock for a user"""
    if user_id not in _progress_locks:
        _progress_locks[user_id] = asyncio.Lock()
    return _progress_locks[user_id]

def cleanup_progress_lock(user_id: str) -> None:
    """Clean up progress lock for a specific user"""
    if user_id in _progress_locks:
        del _progress_locks[user_id]
        logger.info(f"Cleaned up progress lock for user {user_id}")

async def create_progress_callback(message: Any, type_message: str = ""):
    """Create a progress callback function for file operations"""
    async def callback(current: int, total: int) -> None:
        await progress_bar(current, total, message, type_message)
    return callback

def cleanup_all_user_data(user_id: str) -> None:
    """Clean up all data associated with a user"""
    cleanup_user_data(user_id)
    cleanup_progress_lock(user_id)
    # Clean up any message-specific progress data
    for msg_id in list(_progress_trackers.keys()):
        if msg_id.startswith(f"{user_id}_"):
            del _progress_trackers[msg_id]