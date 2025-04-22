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

            # Generate shareable link
            share_link = await generate_link(self.client, uploaded)
            if not share_link:
                raise Exception("Failed to generate share link")

            # Extract the necessary information from post_data
            try:
                # Get data from the nested structure
                data = self.post_data.get(str(self.user_id), {}).get('data', {})
                
                # Create post text with proper formatting and error handling
                post_text = self._format_post_text(data)
            except Exception as e:
                logger.error(f"Error formatting post text: {e}")
                raise Exception("Failed to format post text")

            # Create button for download
            keyboard = [[InlineKeyboardButton("📥 Download", url=share_link)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Send to main channel
            try:
                cover_url = data.get('cover_url')
                if cover_url:
                    # Send with cover photo
                    main_post = await self.client.send_photo(
                        MAIN_CHANNEL,
                        photo=cover_url,
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
            except Exception as e:
                logger.error(f"Failed to send post: {e}")
                raise

            # Clean up
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Failed to remove file: {e}")

            await self.status_msg.edit("✅ Upload complete!")
            if self.channel_msg:
                await self.channel_msg.delete()

            return uploaded.id

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Upload failed: {error_msg}")
            await self.status_msg.edit(f"❌ Upload failed: {error_msg}")
            if self.channel_msg:
                await self.channel_msg.delete()
            return None

    def _format_post_text(self, data):
        """Format the post text with proper error handling"""
        try:
            # Default values in case any field is missing
            title = data.get('title', 'Unknown Title')
            rating = data.get('rating', 'N/A')
            episode = data.get('episode', 'N/A')
            genres = data.get('genres', 'N/A')
            description = data.get('description', 'No synopsis available.')

            # Format the post text with proper spacing
            post_text = f"""☗   {title}

⦿   Ratings: {rating}
⦿   Episode: {episode}
⦿   Genres: {genres}

◆   Synopsis: {description}"""
            
            return post_text
        except Exception as e:
            logger.error(f"Error in _format_post_text: {e}")
            # Return a basic format if something goes wrong
            return "☗   Upload Complete"