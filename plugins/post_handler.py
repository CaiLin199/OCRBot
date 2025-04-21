from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import OWNER_ID, MAIN_CHANNEL
from .shared_data import logger

class PostHandler:
    def __init__(self):
        self.post_data = {}

    @staticmethod
    def _create_post_menu(user_data=None):
        """Create the post creation menu with checkmarks for filled fields"""
        def get_button_text(field, display_name):
            if user_data and field in user_data:
                return f"✅ {display_name}"  # Add checkmark if field is filled
            return display_name

        keyboard = [
            [
                InlineKeyboardButton(get_button_text('title', "Title"), callback_data="title"),
                InlineKeyboardButton(get_button_text('rating', "Rating"), callback_data="rating")
            ],
            [
                InlineKeyboardButton(get_button_text('status', "Status"), callback_data="status"),
                InlineKeyboardButton(get_button_text('episode', "Episode"), callback_data="episode")
            ],
            [
                InlineKeyboardButton(get_button_text('size', "Size"), callback_data="size"),
                InlineKeyboardButton(get_button_text('genres', "Genres"), callback_data="genres")
            ],
            [
                InlineKeyboardButton(get_button_text('synopsis', "Synopsis"), callback_data="synopsis")
            ],
            [
                InlineKeyboardButton("Create Post", callback_data="create_post")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    def format_post(self, data):
        """Format post data according to template"""
        synopsis = data.get('synopsis', 'N/A')
        if len(synopsis) > 100:  # Truncate synopsis if too long
            synopsis = synopsis[:97] + "..."

        template = (
            f"☗   {data.get('title', 'N/A')}\n\n"
            f"⦿   Ratings: {data.get('rating', 'N/A')}\n"
            f"⦿   Status: {data.get('status', 'N/A')}\n"
            f"⦿   Episode: {data.get('episode', 'N/A')}\n"
            f"⦿   Size: {data.get('size', 'N/A')}\n"
            f"⦿   Genres: {data.get('genres', 'N/A')}\n\n"
            f"◆   Synopsis: {synopsis}"
        )
        return template

    async def handle_post_command(self, client, message):
        """Handle /post command"""
        try:
            user_id = message.from_user.id
            self.post_data[user_id] = {}
            
            await message.reply(
                "Please fill in the post details:",
                reply_markup=self._create_post_menu(self.post_data.get(user_id))
            )
        except Exception as e:
            logger.error(f"Post creation failed: {e}")
            await message.reply(f"❌ Error: {str(e)}")

    async def handle_callback(self, client, callback_query):
        """Handle callback queries for post creation"""
        try:
            user_id = callback_query.from_user.id
            data = callback_query.data

            if data == "create_post":
                if user_id not in self.post_data or not self.post_data[user_id]:
                    await callback_query.answer("Please fill in the post details first!")
                    return False, None

                if 'title' not in self.post_data[user_id]:
                    await callback_query.answer("Title is required!")
                    return False, None

                post_text = self.format_post(self.post_data[user_id])
                await callback_query.message.edit_text(post_text)
                return True, callback_query.message

            # Initialize post data for user if not exists
            if user_id not in self.post_data:
                self.post_data[user_id] = {}

            field_prompts = {
                'title': "Enter the title:",
                'rating': "Enter the rating (e.g., 9.8 or 90%):",
                'status': "Enter the status (e.g., Airing):",
                'episode': "Enter the episode number:",
                'size': "Enter the size (e.g., 84.9 MB):",
                'genres': "Enter the genres (comma-separated):",
                'synopsis': "Enter the synopsis:"
            }

            await callback_query.message.edit_text(field_prompts.get(data, f"Enter the {data}:"))
            self.post_data[user_id]['current_field'] = data
            return False, None

        except Exception as e:
            logger.error(f"Callback error: {e}")
            await callback_query.answer("An error occurred", show_alert=True)
            return False, None

    async def handle_input(self, client, message):
        """Handle user input for post fields"""
        try:
            user_id = message.from_user.id
            if user_id not in self.post_data or 'current_field' not in self.post_data[user_id]:
                return

            field = self.post_data[user_id]['current_field']
            text = message.text.strip()

            # Validate input based on field
            if field == 'rating':
                # Accept both percentage and decimal formats
                text = text.replace('%', '').strip()
                try:
                    rating = float(text)
                    if rating > 100:  # Convert 10-point scale to percentage
                        rating = rating / 10
                    text = f"{rating}%"
                except ValueError:
                    await message.reply("Please enter a valid rating number!")
                    return

            # Save the validated input
            self.post_data[user_id][field] = text

            # Show updated post preview
            preview = self.format_post(self.post_data[user_id])
            await message.reply(
                f"✅ {field.title()} set successfully!\n\nPreview:\n\n{preview}",
                reply_markup=self._create_post_menu(self.post_data[user_id])
            )

        except Exception as e:
            logger.error(f"Input handling failed: {e}")
            await message.reply("❌ Error occurred. Please try again.")

    def get_post_data(self, user_id):
        """Get post data for a user"""
        return self.post_data.get(user_id, {})

    def clear_post_data(self, user_id):
        """Clear post data for a user"""
        if user_id in self.post_data:
            del self.post_data[user_id]