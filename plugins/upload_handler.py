import os
from datetime import datetime
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import CHANNEL_ID, MAIN_CHANNEL, THUMBNAIL
from .shared_data import logger
from .link_generation import generate_link

class UploadHandler:
    def __init__(self, client, user_id, status_msg, channel_msg, post_data):
        self.client = client
        self.user_id = user_id
        self.status_msg = status_msg
        self.channel_msg = channel_msg
        self.post_data = post_data.get(str(user_id), {}).get('data', {}) if isinstance(post_data, dict) else {}

    async def progress(self, current, total):
        """Simple progress callback"""
        try:
            percent = f"{current * 100 / total:.1f}%"
            await self.status_msg.edit(f"📤 Uploading: {percent}")
        except:
            pass

    async def upload_file(self, file_path):
        if not os.path.exists(file_path):
            await self.status_msg.edit("❌ File not found!")
            return None

        try:
            # Basic upload with minimal overhead
            uploaded = await self.client.send_document(
                chat_id=CHANNEL_ID,
                document=file_path,
                force_document=True,
                progress=self.progress
            )

            if not uploaded:
                raise Exception("Upload failed")

            # Simple link generation
            share_link = await generate_link(uploaded)
            if not share_link:
                raise Exception("Link generation failed")

            # Create simple post
            post_text = self._create_post()
            keyboard = [[InlineKeyboardButton("📥 Download", url=share_link)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Post to channel
            try:
                cover_url = self.post_data.get('cover_url')
                if cover_url and cover_url.startswith('http'):
                    await self.client.send_photo(
                        MAIN_CHANNEL,
                        photo=cover_url,
                        caption=post_text,
                        reply_markup=reply_markup
                    )
                else:
                    await self.client.send_message(
                        MAIN_CHANNEL,
                        post_text,
                        reply_markup=reply_markup
                    )
            except Exception as e:
                logger.error(f"Post failed: {e}")
                raise

            # Cleanup
            try:
                os.remove(file_path)
            except:
                pass

            await self.status_msg.edit("✅ Done!")
            if self.channel_msg:
                await self.channel_msg.delete()

            return uploaded.id

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            await self.status_msg.edit(f"❌ Failed: {str(e)}")
            if self.channel_msg:
                await self.channel_msg.delete()
            return None

    def _create_post(self):
        """Simple post creation"""
        try:
            title = self.post_data.get('title', '')
            rating = self.post_data.get('rating', '')
            episode = self.post_data.get('episode', '')
            genres = self.post_data.get('genres', '')
            description = self.post_data.get('description', '')

            parts = [f"☗   {title}\n"]
            
            if rating:
                parts.append(f"⦿   Ratings: {rating}")
            if episode:
                parts.append(f"⦿   Episode: {episode}")
            if genres:
                parts.append(f"⦿   Genres: {genres}")
            
            if description:
                parts.append("")
                parts.append(f"◆   Synopsis: {description}")

            return "\n".join(parts)
        except:
            return f"☗   {self.post_data.get('title', '')}"