from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot import Bot
from config import OWNER_IDS
from .shared_data import logger
from .post_handler import PostHandler
from datetime import datetime

class CallbackHandler:
    def __init__(self, post_handler):
        self.post_handler = post_handler
        self.setup_handlers()

    def setup_handlers(self):
        @Bot.on_callback_query()
        async def callback_query_handler(client, callback_query):
            await self._handle_callback(client, callback_query)

    async def _handle_callback(self, client, callback_query):
        """Main callback handler"""
        try:
            user_id = callback_query.from_user.id
            data = callback_query.data

            # Verify user authorization
            if user_id not in OWNER_IDS:
                await callback_query.answer("⚠️ You are not authorized to use this bot.", show_alert=True)
                return

            # Get post data
            post_data = self.post_handler.get_post_data()
            if user_id not in post_data and data != "start_post":
                await callback_query.answer("Session expired. Please start again with /post", show_alert=True)
                return

            # Handle different callback types
            if data == "start_post":
                await self._handle_start_post(callback_query)
            elif data == "create_post":
                await self._handle_create_post(client, callback_query)
            elif data.startswith("set_"):
                await self._handle_field_setting(callback_query, data)
            elif data == "cancel":
                await self._handle_cancel(callback_query, user_id)
            else:
                await self._handle_custom_callback(callback_query, data)

        except Exception as e:
            logger.error(f"Callback handling failed: {e}")
            await self._handle_callback_error(callback_query, str(e))

    async def _handle_start_post(self, callback_query):
        """Handle starting a new post"""
        try:
            user_id = callback_query.from_user.id
            self.post_handler.initialize_post_data(user_id)
            
            buttons = self._create_post_menu(user_id)
            await callback_query.message.edit_text(
                "🎬 <b>Create New Post</b>\n\nPlease fill in the details (Title and DDL are required):",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception as e:
            logger.error(f"Start post handling failed: {e}")
            await self._handle_callback_error(callback_query, str(e))

    async def _handle_create_post(self, client, callback_query):
        """Handle post creation confirmation"""
        try:
            user_id = callback_query.from_user.id
            post_data = self.post_handler.get_post_data()

            # Validate required fields
            missing_fields = self._validate_required_fields(user_id, post_data)
            if missing_fields:
                await callback_query.answer(
                    f"Please fill in required fields: {', '.join(missing_fields)}",
                    show_alert=True
                )
                return

            # Validate field formats
            invalid_fields = await self._validate_field_formats(user_id, post_data)
            if invalid_fields:
                await callback_query.answer(
                    f"Invalid format in fields: {', '.join(invalid_fields)}",
                    show_alert=True
                )
                return

            await callback_query.message.edit_text("Starting download process...")
            return True, self._create_custom_message(client, user_id, callback_query)

        except Exception as e:
            logger.error(f"Create post handling failed: {e}")
            await self._handle_callback_error(callback_query, str(e))
            return False, None

    async def _handle_field_setting(self, callback_query, data):
        """Handle setting individual fields"""
        try:
            user_id = callback_query.from_user.id
            field = data.replace('set_', '')
            
            # Update post data step
            self.post_handler.set_current_step(user_id, field)
            
            # Get field prompt
            prompt = self._get_field_prompt(field)
            
            await callback_query.message.edit_text(prompt)

        except Exception as e:
            logger.error(f"Field setting failed: {e}")
            await self._handle_callback_error(callback_query, str(e))

    async def _handle_cancel(self, callback_query, user_id):
        """Handle cancelling post creation"""
        try:
            self.post_handler.clear_post_data(user_id)
            await callback_query.message.edit_text("❌ Post creation cancelled.")
        except Exception as e:
            logger.error(f"Cancel handling failed: {e}")
            await self._handle_callback_error(callback_query, str(e))

    async def _handle_custom_callback(self, callback_query, data):
        """Handle any custom callbacks"""
        try:
            # Add custom callback handling here
            await callback_query.answer(f"Handling: {data}")
        except Exception as e:
            logger.error(f"Custom callback handling failed: {e}")
            await self._handle_callback_error(callback_query, str(e))

    async def _handle_callback_error(self, callback_query, error_message):
        """Handle callback errors"""
        try:
            await callback_query.answer(
                "An error occurred. Please try again.",
                show_alert=True
            )
            logger.error(f"Callback error: {error_message}")
        except:
            pass

    def _create_post_menu(self, user_id):
        """Create the post creation menu with checkmarks"""
        post_data = self.post_handler.get_post_data()
        return [
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
                f"{'✅' if 'genres' in post_data[user_id]['data'] else ''} Genres", 
                callback_data="set_genres"
            )],
            [InlineKeyboardButton("✅ Create Post", callback_data="create_post")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ]

    def _validate_required_fields(self, user_id, post_data):
        """Validate required fields are filled"""
        required_fields = ['title', 'ddl']
        return [field for field in required_fields 
                if field not in post_data[user_id]['data']]

    async def _validate_field_formats(self, user_id, post_data):
        """Validate field formats"""
        invalid_fields = []
        user_data = post_data[user_id]['data']

        # Validate rating (0-100)
        if 'rating' in user_data:
            try:
                rating = int(user_data['rating'])
                if not (0 <= rating <= 100):
                    invalid_fields.append('rating')
            except ValueError:
                invalid_fields.append('rating')

        # Validate episode number (numeric)
        if 'episode' in user_data:
            if not user_data['episode'].replace('.', '').isdigit():
                invalid_fields.append('episode')

        return invalid_fields

    def _get_field_prompt(self, field):
        """Get prompt text for each field"""
        prompts = {
            'title': "Please send the title for the post:",
            'ddl': "Please send the direct download link:",
            'rating': "Please send the rating (0-100):",
            'description': "Please send the description/synopsis:",
            'episode': "Please send the episode number:",
            'genres': "Please send the genres (comma-separated):"
        }
        return prompts.get(field, f"Please send the {field.replace('_', ' ')} for the post:")

    def _create_custom_message(self, client, user_id, callback_query):
        """Create a custom message object for DDL handling"""
        post_data = self.post_handler.get_post_data()
        
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

        return CustomMessage(
            client,
            post_data[user_id]['data']['ddl'],
            user_id,
            callback_query
        )

# Initialize the callback handler
callback_handler = CallbackHandler(post_handler=PostHandler())