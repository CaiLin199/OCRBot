from datetime import datetime
from pyrogram.types import Message
from config import MAIN_CHANNEL

class ProgressHandler:
    def __init__(self, client, user_message):
        self.client = client
        self.user_message = user_message
        self.channel_msg = None
        self.status_msg = None
        self.start_time = None
        self.last_update_time = datetime.now()
        self.update_interval = 2  # Update every 2 seconds to avoid flood

    async def init_messages(self, filename):
        """Initialize progress messages in both PM and channel"""
        self.status_msg = await self.user_message.reply("📥 Starting Download...")
        self.channel_msg = await self.client.send_message(
            MAIN_CHANNEL,
            f"🤖 **Bot Processing New File**\n\n"
            f"**File:** `{filename}`\n"
            f"**Status:** Initializing download..."
        )
        self.start_time = datetime.now()
        return self.status_msg

    def get_progress_bar(self, current, total):
        """Generate a progress bar"""
        percentage = current * 100 / total
        bar_length = 10
        filled_length = int(percentage / 100 * bar_length)
        bar = '■' * filled_length + '□' * (bar_length - filled_length)
        return bar, percentage

    def get_progress_text(self, current, total, status, filename):
        """Generate progress text with percentage and speed"""
        now = datetime.now()
        diff = (now - self.start_time).seconds
        
        speed = current / diff if diff > 0 else 0
        bar, percentage = self.get_progress_bar(current, total)
        
        progress_text = (
            f"🤖 **Bot Processing New File**\n\n"
            f"**File:** `{filename}`\n"
            f"**Status:** {status}\n\n"
            f"```{bar}``` {percentage:.1f}%\n"
            f"⚡️ **Speed:** {self.humanbytes(speed)}/s\n"
            f"📊 **Size:** {self.humanbytes(current)} / {self.humanbytes(total)}"
        )
        
        return progress_text

    async def update_progress(self, current, total, status, filename):
        """Update progress in both PM and channel"""
        try:
            now = datetime.now()
            if (now - self.last_update_time).seconds < self.update_interval:
                return
            
            self.last_update_time = now
            
            # Get progress text for channel
            channel_text = self.get_progress_text(current, total, status, filename)
            
            # Get progress text for PM
            bar, percentage = self.get_progress_bar(current, total)
            speed = current / (now - self.start_time).seconds if (now - self.start_time).seconds > 0 else 0
            
            pm_text = (
                f"**{status}**\n\n"
                f"```{bar}``` {percentage:.1f}%\n"
                f"⚡️ **Speed:** {self.humanbytes(speed)}/s\n"
                f"📊 **Size:** {self.humanbytes(current)} / {self.humanbytes(total)}"
            )
            
            # Update both messages
            if self.channel_msg:
                await self.channel_msg.edit(channel_text)
            if self.status_msg:
                await self.status_msg.edit(pm_text)
                
        except Exception as e:
            print(f"Progress update failed: {str(e)}")

    async def update_status(self, status, filename):
        """Update processing status in both PM and channel"""
        try:
            channel_text = (
                f"🤖 **Bot Processing New File**\n\n"
                f"**File:** `{filename}`\n"
                f"**Status:** {status}"
            )
            
            if self.status_msg:
                await self.status_msg.edit(f"**{status}**")
            if self.channel_msg:
                await self.channel_msg.edit(channel_text)
        except Exception as e:
            print(f"Status update failed: {str(e)}")

    async def finished(self, success=True):
        """Clean up channel message when process is complete"""
        try:
            if self.channel_msg:
                if not success:
                    await self.channel_msg.edit(
                        "❌ **Process Failed**\n\n"
                        "Bot will retry automatically."
                    )
                await self.channel_msg.delete()
        except Exception as e:
            print(f"Failed to delete channel message: {str(e)}")

    @staticmethod
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