from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot import Bot
from config import OWNER_IDS, POST_FORMAT, MAIN_CHANNEL
from .shared_data import logger, user_data
from .upload_handler import UploadHandler

class PostHandler:
    def __init__(self):
        self.post_data = {}

    @staticmethod
    def _create_post_menu(user_id, post_data):
        """Create the post creation menu with checkmarks for filled fields"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(
                f"{'✅' if 'title' in post_data[user_id]['data'] else ''} Title (Required)", 
                callback_data="set_title"
            )],
            [InlineKeyboardButton(
                f"{'✅' if 'ddl' in post_data[user_id]['data'] else ''} Direct Download Link (Required)", 
                callback_data="set_ddl"
            )],
            [InlineKeyboardButton(
                f"{'✅' if 'rating' in post_data[user_id]['data'] else ''} Rating (0-100)", 
                callback_data="set_rating"
            )],
            [InlineKeyboardButton(
                f"{'✅' if 'description' in post_data[user_id]['data'] else ''} Description", 
                callback_data="set_description"
            )],
            [InlineKeyboardButton(
                f"{'✅' if 'episode' in post_data[user_id]['data'] else ''} Episode Number", 
                callback_data="set_episode"
            )],
            [InlineKeyboardButton(
                f"{'✅' if 'cover' in post_data[user_id]['data'] else ''} Cover Image URL", 
                callback_data="set_cover"
            )],
            [InlineKeyboardButton(
                f"{'✅' if 'genres' in post_data[user_id]['data'] else ''} Genres", 
                callback_data="set_genres"
            )],
            [InlineKeyboardButton("✅ Create Post", callback_data="create_post")]
        ])

    async def validate_rating(self, rating_text):
        """Validate rating is between 0-100"""
        try:
            rating = int(rating_text)
            if 0 <= rating <= 100:
                return True
            return False
        except ValueError:
            return False

    async def handle_post_command(self, client, message):
        """Handle the /post command"""
        try:
            user_id = message.from_user.id
            self.post_data[user_id] = {
                "step": "rating",
                "data": {}
            }

            await message.reply(
                "🎬 <b>Create New Post</b>\n\nPlease fill in the details (Title and DDL are required):",
                reply_markup=self._create_post_menu(user_id, self.post_data)
            )

        except Exception as e:
            logger.error(f"Post creation failed: {e}")
            await message.reply(f"❌ Error: {str(e)}")

    async def handle_callback(self, client, callback_query):
        """Handle callback queries for post creation"""
        try:
            user_id = callback_query.from_user.id
            data = callback_query.data

            if user_id not in self.post_data:
                return await callback_query.answer("Session expired. Please start again with /post")

            if data == "create_post":
                return await self._handle_create_post(client, callback_query, user_id)

            # Handle different input fields
            field = data.replace('set_', '')
            self.post_data[user_id]['step'] = field
            
            field_prompts = {
                'title': "Please send the title for the post:",
                'ddl': "Please send the direct download link:",
                'rating': "Please send the rating (0-100):",
                'description': "Please send the description/synopsis:",
                'episode': "Please send the episode number:",
                'cover': "Please send the cover image URL:",
                'genres': "Please send the genres (comma-separated):"
            }
            
            await callback_query.message.edit_text(
                field_prompts.get(field, f"Please send the {field.replace('_', ' ')} for the post:")
            )

        except Exception as e:
            logger.error(f"Callback handling failed: {e}")
            await callback_query.answer("An error occurred. Please try again.", show_alert=True)

    async def _handle_create_post(self, client, callback_query, user_id):
        """Handle the creation of the post"""
        # Check required fields
        required_fields = ['title', 'ddl']
        missing_fields = [field for field in required_fields 
                         if field not in self.post_data[user_id]['data']]
        
        if missing_fields:
            return await callback_query.answer(
                f"Please fill in required fields: {', '.join(missing_fields)}",
                show_alert=True
            )

        # Create a proper message-like object for DDL handling
        class CustomMessage:
            def __init__(self, client, url, user_id, callback_query):
                self.command = ['ddl', url]
                self.from_user = type('User', (), {'id': user_id})()
                self._client = client
                self._callback_query = callback_query

            async def reply(self, text, **kwargs):
                try:
                    return await self._callback_query.message.reply(text)
                except Exception as e:
                    logger.error(f"Reply failed: {e}")
                    return None

        try:
            await callback_query.message.edit_text("Starting download process...")
            ddl_url = self.post_data[user_id]['data']['ddl']
            custom_msg = CustomMessage(client, ddl_url, user_id, callback_query)
            
            # The DDL handler will be called from video_handler.py
            return True, custom_msg

        except Exception as e:
            logger.error(f"Post creation failed: {e}")
            await callback_query.message.edit_text(f"❌ Failed: {str(e)}")
            return False, None

    async def handle_input(self, client, message):
        """Handle user input during post creation"""
        try:
            user_id = message.from_user.id
            
            if user_id not in self.post_data:
                return

            step = self.post_data[user_id]['step']

            # Validate rating if that's the current step
            if step == 'rating' and not await self.validate_rating(message.text):
                await message.reply("Please send a valid rating between 0 and 100.")
                return

            # Save the input
            self.post_data[user_id]['data'][step] = message.text

            # Show updated menu
            await message.reply(
                "🎬 <b>Create New Post</b>\n\nPlease fill in the remaining details (Title and DDL are required):",
                reply_markup=self._create_post_menu(user_id, self.post_data)
            )

        except Exception as e:
            logger.error(f"Input handling failed: {e}")
            await message.reply("An error occurred. Please try again with /post")

    def get_post_data(self):
        """Get the current post data"""
        return self.post_data

    def clear_post_data(self, user_id):
        """Clear post data for a user"""
        if user_id in self.post_data:
            del self.post_data[user_id]