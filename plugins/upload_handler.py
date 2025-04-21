import os
from datetime import datetime
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import CHANNEL_ID, MAIN_CHANNEL, THUMBNAIL
from .shared_data import logger
from .link_generation import generate_link
from .progress import Progress

class UploadHandler:
    def __init__(self, client, user_id, status_msg, channel_msg, post_data):
        self.client = client
        self.user_id = user_id
        self.status_msg = status_msg
        self.channel_msg = channel_msg
        self.post_data = post_data
        self.progress = Progress(client, status_msg, channel_msg, action="📤 Uploading to channel...")

    async def upload_file(self, file_path):
        try:
            # Check for thumbnail
            thumbnail = THUMBNAIL
            if not os.path.exists(thumbnail):
                logger.warning(f"Thumbnail not found at {thumbnail}")
                thumbnail = None

            # Upload with progress
            uploaded = await self.client.send_document(
                CHANNEL_ID,
                file_path,
                force_document=True,
                thumb=thumbnail,
                progress=self.progress.update_progress
            )

            # Generate shareable link
            share_link = await generate_link(self.client, uploaded)
            
            # Create post text
            post_text = await self._create_post_text(share_link)
            
            # Send to main channel
            main_post = await self.client.send_message(
                MAIN_CHANNEL,
                post_text,
                disable_web_page_preview=True
            )

            # Clean up
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Failed to remove file: {e}")

            await self.status_msg.edit("✅ Upload complete!")
            await self.channel_msg.delete()

            return True

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Upload failed: {error_msg}")
            
            if "genras" in error_msg:  # Handle specific error
                error_msg = "Invalid genres format. Please make sure genres are properly formatted."
            
            await self.status_msg.edit(f"❌ Upload failed: {error_msg}")
            await self.channel_msg.delete()
            return False

    async def _create_post_text(self, share_link):
        """Create the post text with all available information"""
        try:
            post_components = []

            # Add title (required)
            title = self.post_data[self.user_id]['data'].get('title', 'No Title')
            post_components.append(f"🎬 **{title}**\n")

            # Add description if available
            if description := self.post_data[self.user_id]['data'].get('description'):
                post_components.append(f"📝 **Description:** {description}\n")

            # Add rating if available
            if rating := self.post_data[self.user_id]['data'].get('rating'):
                post_components.append(f"⭐️ **Rating:** {rating}%\n")

            # Add episode if available
            if episode := self.post_data[self.user_id]['data'].get('episode'):
                post_components.append(f"📺 **Episode:** {episode}\n")

            # Add genres if available
            if genres := self.post_data[self.user_id]['data'].get('genres'):
                post_components.append(f"🎭 **Genres:** {genres}\n")

            # Add download link
            post_components.append(f"📥 **Download:** {share_link}")

            # Join all components and clean empty lines
            post_text = "\n".join(post_components)
            post_text = "\n".join(line for line in post_text.split('\n') if line.strip())

            return post_text

        except Exception as e:
            logger.error(f"Failed to create post text: {e}")
            raise e