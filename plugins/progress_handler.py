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

    async def init_messages(self):
        """Initialize progress messages in both PM and channel"""
        self.status_msg = await self.user_message.reply("📥 Starting Download...")
        self.channel_msg = await self.client.send_message(
            MAIN_CHANNEL,
            "🔄 **New File Processing Started**\n\n💫 Initializing download..."
        )
        self.start_time = datetime.now()
        return self.status_msg

    def get_progress_text(self, current, total, status):
        """Generate progress text with percentage and speed"""
        now = datetime.now()
        diff = (now - self.start_time).seconds
        
        # Calculate speed and progress
        speed = current / diff if diff > 0 else 0
        percentage = (current * 100) / total
        
        # Format progress bar
        bar_length = 10
        filled_length = int(percentage / 100 * bar_length)
        bar = '■' * filled_length + '□' * (bar_length - filled_length)
        
        progress_text = f"🔄 **New File Processing**\n\n"
        progress_text += f"**{status}**\n"
        progress_text += f"```{bar}``` {percentage:.1f}%\n\n"
        progress_text += f"⚡️ **Speed:** {self.humanbytes(speed)}/s\n"
        progress_text += f"📊 **Progress:** {self.humanbytes(current)} / {self.humanbytes(total)}"
        
        return progress_text

    async def update_progress(self, current, total, status="Downloading"):
        """Update progress in both PM and channel"""
        try:
            now = datetime.now()
            # Only update if enough time has passed since last update
            if (now - self.last_update_time).seconds < self.update_interval:
                return
            
            self.last_update_time = now
            progress_text = self.get_progress_text(current, total, status)
            
            # Update channel message
            if self.channel_msg:
                await self.channel_msg.edit(progress_text)
            
            # Update PM message with more detailed progress
            if self.status_msg:
                await self.status_msg.edit(
                    f"{status}\n\n"
                    f"📊 **Progress:** {current * 100 / total:.1f}%\n"
                    f"📦 **Size:** {self.humanbytes(current)} / {self.humanbytes(total)}\n"
                    f"⚡️ **Speed:** {self.humanbytes(current/(now - self.start_time).seconds)}/s"
                )
                
        except Exception as e:
            print(f"Progress update failed: {str(e)}")

    async def update_status(self, text):
        """Update status messages with new text"""
        try:
            if self.status_msg:
                await self.status_msg.edit(text)
            if self.channel_msg:
                await self.channel_msg.edit(
                    f"🔄 **New File Processing**\n\n"
                    f"**Status:** {text}"
                )
        except Exception as e:
            print(f"Status update failed: {str(e)}")

    async def finished(self):
        """Clean up channel message when process is complete"""
        try:
            if self.channel_msg:
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