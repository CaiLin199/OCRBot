# commented out don't use this codes
'''
from datetime import datetime
from pyrogram.types import Message
from config import MAIN_CHANNEL

async def progress_bar(current, total, status_msg, start_time, status_text):
    """Show progress bar for operations"""
    try:
        now = datetime.now()
        diff = (now - start_time).seconds
        
        if diff == 0:
            return
            
        speed = current / diff if diff > 0 else 0
        percentage = current * 100 / total
        
        # Calculate ETA
        if speed > 0:
            eta = (total - current) / speed
            eta_hours = int(eta // 3600)
            eta_minutes = int((eta % 3600) // 60)
            eta_seconds = int(eta % 60)
        else:
            eta_hours = eta_minutes = eta_seconds = 0
            
        # Calculate elapsed time
        elapsed_minutes = diff // 60
        elapsed_seconds = diff % 60
        
        # Progress bar
        bar_length = 10
        filled_length = int(percentage / 100 * bar_length)
        bar = '[' + '■' * filled_length + '□' * (bar_length - filled_length) + ']'
        
        # Format message
        status_text = (
            f"Progress: {bar} {percentage:.1f}%\n"
            f"📥 {status_text}: {humanbytes(current)} | {humanbytes(total)}\n"
            f"⚡️ Speed: {humanbytes(speed)}/s\n"
            f"⌛ ETA: {eta_hours}h {eta_minutes}m {eta_seconds}s\n"
            f"⏱️ Time elapsed: {elapsed_minutes}m {elapsed_seconds}s"
        )
        
        await status_msg.edit(status_text)
    except Exception as e:
        print(f"Progress update failed: {str(e)}")

def humanbytes(size):
    """Convert bytes to human readable format"""
    if not size:
        return "0B"
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{size:.2f}{units[index]}"

class ProgressHandler:
    def __init__(self, client, user_message):
        self.client = client
        self.user_message = user_message
        self.channel_msg = None
        self.status_msg = None
        self.start_time = None
        self.last_update_time = datetime.now()
        self.update_interval = 7

    async def init_messages(self):
        """Initialize progress messages in both PM and channel"""
        self.status_msg = await self.user_message.reply("📥 Starting Download...")
        self.channel_msg = await self.client.send_message(
            MAIN_CHANNEL,            
            "Status: Initializing..."
        )
        self.start_time = datetime.now()
        return self.status_msg

    def get_progress_bar(self, current, total):
        """Generate a progress bar"""
        percentage = current * 100 / total
        bar_length = 10
        filled_length = int(percentage / 100 * bar_length)
        bar = '[' + '■' * filled_length + '□' * (bar_length - filled_length) + ']'
        return bar, percentage

    async def update_progress(self, current, total, status):
        """Update progress in both PM and channel"""
        try:
            now = datetime.now()
            if (now - self.last_update_time).seconds < self.update_interval:
                return
            
            self.last_update_time = now
            
            # Calculate times
            diff = (now - self.start_time).seconds
            speed = current / diff if diff > 0 else 0
            
            # Calculate ETA
            if speed > 0:
                eta = (total - current) / speed
                eta_hours = int(eta // 3600)
                eta_minutes = int((eta % 3600) // 60)
                eta_seconds = int(eta % 60)
            else:
                eta_hours = eta_minutes = eta_seconds = 0
                
            # Calculate elapsed time
            elapsed_minutes = diff // 60
            elapsed_seconds = diff % 60
            
            # Get progress bar
            bar, percentage = self.get_progress_bar(current, total)
            
            # Channel text
            channel_text = (
                f"Progress: {bar} {percentage:.1f}%\n"
                f"📥 {status}: {humanbytes(current)} | {humanbytes(total)}\n"
                f"⚡️ Speed: {humanbytes(speed)}/s\n"
                f"⌛ ETA: {eta_hours}h {eta_minutes}m {eta_seconds}s\n"
                f"⏱️ Time elapsed: {elapsed_minutes}m {elapsed_seconds}s"
            )
            
            # PM text (same format)
            pm_text = channel_text
            
            # Update both messages with try-except for each
            if self.channel_msg:
                try:
                    await self.channel_msg.edit(channel_text)
                except Exception as e:
                    if "420 FLOOD_WAIT" not in str(e):
                        print(f"Channel update failed: {str(e)}")
                    
            if self.status_msg:
                try:
                    await self.status_msg.edit(pm_text)
                except Exception as e:
                    if "420 FLOOD_WAIT" not in str(e):
                        print(f"PM update failed: {str(e)}")
                
        except Exception as e:
            print(f"Progress update failed: {str(e)}")

    async def update_status(self, status):
        """Update processing status in both PM and channel"""
        try:
            status_text = f"Status: {status}"
            
            if self.status_msg:
                try:
                    await self.status_msg.edit(status_text)
                except Exception as e:
                    if "420 FLOOD_WAIT" not in str(e):
                        print(f"PM status update failed: {str(e)}")
                    
            if self.channel_msg:
                try:
                    await self.channel_msg.edit(status_text)
                except Exception as e:
                    if "420 FLOOD_WAIT" not in str(e):
                        print(f"Channel status update failed: {str(e)}")
        except Exception as e:
            print(f"Status update failed: {str(e)}")

    async def finished(self, success=True):
        """Clean up channel message when process is complete"""
        try:
            if self.channel_msg:
                if not success:
                    await self.channel_msg.edit("Process Failed")
                await self.channel_msg.delete()
        except Exception as e:
            print(f"Failed to delete channel message: {str(e)}") 