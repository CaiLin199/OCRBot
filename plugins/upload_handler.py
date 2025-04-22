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

            if not uploaded:
                raise Exception("Upload failed: No response from Telegram")

            # Get message ID
            msg_id = uploaded.id

            # Generate shareable link
            share_link = await generate_link(self.client, uploaded)
            
            # Create post text
            post_text = await self._create_post_text(share_link)
            
            # Create button for download
            keyboard = [[InlineKeyboardButton("📥 Download", url=share_link)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Send to main channel
            if self.post_data and isinstance(self.post_data, dict) and 'data' in self.post_data and 'cover_url' in self.post_data['data']:
                # Send with cover photo
                main_post = await self.client.send_photo(
                    MAIN_CHANNEL,
                    photo=self.post_data['data']['cover_url'],
                    caption=post_text,
                    reply_markup=reply_markup
                )
            else:
                # Send without cover
                main_post = await self.client.send_message(
                    MAIN_CHANNEL,
                    post_text,
                    disable_web_page_preview=True,
                    reply_markup=reply_markup
                )

            # Clean up
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Failed to remove file: {e}")

            await self.status_msg.edit("✅ Upload complete!")
            await self.channel_msg.delete()

            return msg_id

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Upload failed: {error_msg}")
            await self.status_msg.edit(f"❌ Upload failed: {error_msg}")
            await self.channel_msg.delete()
            return None

    async def _create_post_text(self, share_link):
        """Create the post text with exact formatting"""
        try:
            if not self.post_data or not isinstance(self.post_data, dict) or 'data' not in self.post_data:
                return f"☗ File Upload\n\n📥 Download: {share_link}"

            post_components = []
            user_data = self.post_data['data']

            # Title
            title = user_data.get('title', 'No Title')
            post_components.append(f"☗   {title}\n")

            # Ratings
            if rating := user_data.get('rating'):
                post_components.append(f"⦿   Ratings: {rating}")

            # Episode
            if episode := user_data.get('episode'):
                post_components.append(f"⦿   Episode: {episode}")

            # Quality
            if quality := user_data.get('quality', '720p'):
                post_components.append(f"⦿   Quality: {quality}")

            # Genres
            if genres := user_data.get('genres'):
                post_components.append(f"⦿   Genres: {genres}")

            # Add empty line before synopsis
            post_components.append("")

            # Synopsis
            if synopsis := user_data.get('synopsis'):
                # Truncate synopsis if too long
                if len(synopsis) > 100:
                    synopsis = synopsis[:97] + "..."
                post_components.append(f"◆   Synopsis: {synopsis}")

            # Join components
            post_text = "\n".join(post_components)
            
            return post_text

        except Exception as e:
            logger.error(f"Failed to create post text: {e}")
            # Return a basic format instead of raising the error
            return f"☗ File Upload\n\n📥 Download: {share_link}"