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

            post_text = f"""☗   {self.post_data['title']}

⦿   Ratings: {self.post_data['rating']}
⦿   Episode: {self.post_data['episode']}
⦿   Genres: {self.post_data['genres']}

◆   Synopsis: {self.post_data['description']}"""
            
            # Create button for download
            keyboard = [[InlineKeyboardButton("📥 Download", url=share_link)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Send to main channel
            try:
                if 'cover_url' in self.post_data:
                    # Send with cover photo
                    main_post = await self.client.send_photo(
                        MAIN_CHANNEL,
                        photo=self.post_data['cover_url'],
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