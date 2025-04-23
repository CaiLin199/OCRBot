from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

class PostHandler:
    def __init__(self):
        self.current_field = None  # Store the current field being edited
        self.inputs = {}  # Store user inputs for marking buttons with ✅




    def create_post_menu(self):        
        def mark_button(field_name, display_name):
            # If the field is filled, add a ✅ to the button label
            return f"✅ {display_name}" if field_name in self.inputs else display_name

        keyboard = [
            [
                InlineKeyboardButton(mark_button("title", "Title"), callback_data="title"),
                InlineKeyboardButton(mark_button("rating", "Rating"), callback_data="rating")
            ],
            [
                InlineKeyboardButton(mark_button("status", "Status"), callback_data="status"),
                InlineKeyboardButton(mark_button("episode", "Episode"), callback_data="episode")
            ],
            [
                InlineKeyboardButton(mark_button("size", "Size"), callback_data="size"),
                InlineKeyboardButton(mark_button("genres", "Genres"), callback_data="genres")
            ],
            [
                InlineKeyboardButton(mark_button("synopsis", "Synopsis"), callback_data="synopsis"),
                InlineKeyboardButton(mark_button("cover_url", "Cover URL"), callback_data="cover_url")
            ],
            [
                InlineKeyboardButton(mark_button("ddl", "Direct Link"), callback_data="ddl")
            ],
            [
                InlineKeyboardButton("CREATE POST", callback_data="create_post")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def handle_post_command(self, client, message):
        """Handle /post command"""
        self.inputs = {}  # Reset inputs
        self.current_field = None  # Reset the current field

        await message.reply(
            "Please fill in the post details:",
            reply_markup=self.create_post_menu()
        )

    async def handle_callback(self, client, callback_query):
        """Handle button clicks"""
        data = callback_query.data

        if data == "create_post":
            # Format and send final post as a message
            post_text = "\n".join(f"{key.title()}: {value}" for key, value in self.inputs.items())
            await callback_query.message.edit_text(
                post_text if post_text else "No inputs provided."
            )
            return

        # Store the current field to prompt the user
        self.current_field = data

        # Prompt the user for input
        await callback_query.message.edit_text(f"Enter the value for {data.title()}:")

    async def handle_input(self, client, message):
        """Handle user input for fields"""
        if not self.current_field:
            return  # No field is currently being edited

        # Save the input value
        field = self.current_field
        value = message.text.strip()
        self.inputs[field] = value  # Store in inputs dictionary

        # Show updated menu with ✅ marks for completed fields
        await message.reply(
            f"{field.title()} updated to: {value}",
            reply_markup=self.create_post_menu()
        )

        # Clear the current field after input
        self.current_field = None