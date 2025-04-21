import os
import asyncio
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot import Bot
from config import OWNER_IDS, MAIN_CHANNEL, CHANNEL_ID, POST_FORMAT
from datetime import datetime
from .shared_data import user_data, is_auto_mode, logger
from .link_generation import generate_link
from .aria2_client import aria2

# Store post details temporarily
post_data = {}

@Bot.on_message(filters.command('ddl') & filters.user(OWNER_IDS))
async def handle_ddl(client, message):
    try:
        # Check if URL is provided
        if len(message.command) < 2:
            return await message.reply("Please provide a direct download link!\nUsage: /ddl <url>")

        url = message.command[1]
        
        # Create initial status messages
        status_msg = await message.reply("📥 Starting Download...")
        channel_msg = await client.send_message(
            MAIN_CHANNEL,
            "Status: Starting download..."
        )
        start_time = datetime.now()
        last_update_time = datetime.now()

        try:
            # Add download to aria2
            download = aria2.add_uris([url])
            file_path = None

            while not download.is_complete:
                download.update()
                current = download.completed_length
                total = download.total_length
                
                now = datetime.now()
                if (now - last_update_time).seconds >= 7:  # Update every 7 seconds
                    last_update_time = now
                    progress_text = create_progress_text(current, total, start_time)
                    
                    try:
                        await status_msg.edit(progress_text)
                        await channel_msg.edit(progress_text)
                    except Exception as e:
                        if "420 FLOOD_WAIT" not in str(e):
                            logger.error(f"Progress update failed: {str(e)}")
                
                await asyncio.sleep(1)

            if download.is_complete:
                file_path = download.files[0].path
                
            if file_path and os.path.exists(file_path):
                # Upload to channel
                await upload_and_generate_link(client, file_path, message.from_user.id, status_msg, channel_msg)
            else:
                await status_msg.edit("❌ Download failed!")
                await channel_msg.delete()

        except Exception as e:
            logger.error(f"Download failed: {e}")
            await status_msg.edit(f"❌ Download failed: {str(e)}")
            await channel_msg.delete()

    except Exception as e:
        logger.error(f"DDL processing failed: {e}")
        await message.reply(f"❌ Error: {str(e)}")
        if 'channel_msg' in locals():
            await channel_msg.delete()

@Bot.on_message(filters.command('post') & filters.user(OWNER_IDS))
async def handle_post(client, message):
    try:
        user_id = message.from_user.id
        post_data[user_id] = {
            "step": "rating",
            "data": {}
        }

        buttons = [
            [InlineKeyboardButton("Title (Required)", callback_data="set_title")],
            [InlineKeyboardButton("Direct Download Link (Required)", callback_data="set_ddl")],
            [InlineKeyboardButton("Rating", callback_data="set_rating")],
            [InlineKeyboardButton("Description", callback_data="set_description")],
            [InlineKeyboardButton("Episode Number", callback_data="set_episode")],
            [InlineKeyboardButton("Cover Image URL", callback_data="set_cover")],
            [InlineKeyboardButton("Genres", callback_data="set_genres")],
            [InlineKeyboardButton("✅ Create Post", callback_data="create_post")]
        ]

        await message.reply(
            "🎬 <b>Create New Post</b>\n\nPlease fill in the details (Title and DDL are required):",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        logger.error(f"Post creation failed: {e}")
        await message.reply(f"❌ Error: {str(e)}")

async def upload_and_generate_link(client, file_path, user_id, status_msg, channel_msg):
    try:
        await status_msg.edit("📤 Uploading to channel...")
        await channel_msg.edit("Status: Uploading to channel...")
        
        start_time = datetime.now()
        last_update_time = datetime.now()

        async def upload_progress(current, total):
            nonlocal last_update_time
            now = datetime.now()
            
            if (now - last_update_time).seconds < 7:
                return
                
            last_update_time = now
            progress_text = create_progress_text(current, total, start_time)
            
            try:
                await status_msg.edit(f"📤 Uploading...\n\n{progress_text}")
                await channel_msg.edit(f"Status: Uploading...\n\n{progress_text}")
            except Exception as e:
                if "420 FLOOD_WAIT" not in str(e):
                    logger.error(f"Upload progress update failed: {str(e)}")

        thumbnail = "Assist/thumbnail.jpg"
        if not os.path.exists(thumbnail):
            logger.warning(f"Thumbnail not found at {thumbnail}")
            thumbnail = None

        # Upload file
        uploaded = await client.send_document(
            CHANNEL_ID,
            file_path,
            force_document=True,
            thumb=thumbnail,
            progress=upload_progress
        )

        # Generate shareable link
        share_link = await generate_link(client, uploaded)
        
        # Create post with generated link
        post_text = POST_FORMAT.format(
            title=post_data[user_id]['data'].get('title', 'No Title'),
            description=post_data[user_id]['data'].get('description', ''),
            rating=f"{post_data[user_id]['data'].get('rating', '')}%" if post_data[user_id]['data'].get('rating') else '',
            episode=post_data[user_id]['data'].get('episode', ''),
            genres=post_data[user_id]['data'].get('genres', ''),
            link=share_link
        )

        # Clean up empty lines from optional fields
        post_text = '\n'.join(line for line in post_text.split('\n') if line.strip())

        # Send to main channel
        main_post = await client.send_message(
            MAIN_CHANNEL,
            post_text,
            disable_web_page_preview=True
        )

        # Clean up
        try:
            os.remove(file_path)
        except:
            pass

        await status_msg.edit("✅ Upload complete!")
        await channel_msg.delete()

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        await status_msg.edit(f"❌ Upload failed: {str(e)}")
        await channel_msg.delete()

def create_progress_text(current, total, start_time):
    now = datetime.now()
    diff = (now - start_time).seconds
    
    speed = current / diff if diff > 0 else 0
    percentage = current * 100 / total if total > 0 else 0
    
    if speed > 0:
        eta = (total - current) / speed
    else:
        eta = 0
    
    eta_str = str(datetime.fromtimestamp(eta) - datetime.fromtimestamp(0))
    elapsed_time = str(datetime.fromtimestamp(diff) - datetime.fromtimestamp(0))
    
    bar_length = 20
    filled_length = int(percentage * bar_length / 100)
    bar = '█' * filled_length + '▒' * (bar_length - filled_length)
    
    return (
        f"Progress: [{bar}] {percentage:.1f}%\n"
        f"Size: {humanbytes(current)} / {humanbytes(total)}\n"
        f"Speed: {humanbytes(speed)}/s\n"
        f"ETA: {eta_str}\n"
        f"Elapsed: {elapsed_time}"
    )

def humanbytes(size):
    if not size:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    index = 0
    while size >= 1024.0 and index < len(units) - 1:
        size /= 1024.0
        index += 1
        
    return f"{size:.2f} {units[index]}"

@Bot.on_callback_query()
async def handle_callbacks(client, callback_query):
    try:
        user_id = callback_query.from_user.id
        data = callback_query.data

        if user_id not in post_data:
            return await callback_query.answer("Session expired. Please start again with /post")

        if data == "create_post":
            # Check only for title and ddl as mandatory fields
            required_fields = ['title', 'ddl']
            missing_fields = [field for field in required_fields if field not in post_data[user_id]['data']]
            
            if missing_fields:
                return await callback_query.answer(
                    f"Please fill in required fields: {', '.join(missing_fields)}",
                    show_alert=True
                )

            # Create a proper message-like object
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

            # Start download and upload process
            try:
                await callback_query.message.edit_text("Starting download process...")
                ddl_url = post_data[user_id]['data']['ddl']
                custom_msg = CustomMessage(client, ddl_url, user_id, callback_query)
                await handle_ddl(client, custom_msg)
            except Exception as e:
                logger.error(f"DDL processing failed: {e}")
                await callback_query.message.edit_text(f"❌ Download failed: {str(e)}")
            
            # Clear post data
            del post_data[user_id]
            return

        # Handle different input fields
        field = data.replace('set_', '')
        post_data[user_id]['step'] = field
        
        await callback_query.message.edit_text(
            f"Please send the {field.replace('_', ' ')} for the post:"
        )

    except Exception as e:
        logger.error(f"Callback handling failed: {e}")
        await callback_query.answer("An error occurred. Please try again.", show_alert=True)

@Bot.on_message(filters.private & filters.user(OWNER_IDS))
async def handle_post_input(client, message):
    try:
        user_id = message.from_user.id
        
        if user_id not in post_data:
            return
        
        step = post_data[user_id]['step']
        post_data[user_id]['data'][step] = message.text
        
        # Show updated post creation menu
        buttons = [
            [InlineKeyboardButton(f"{'✅' if 'title' in post_data[user_id]['data'] else ''} Title (Required)", 
                                callback_data="set_title")],
            [InlineKeyboardButton(f"{'✅' if 'ddl' in post_data[user_id]['data'] else ''} Direct Download Link (Required)", 
                                callback_data="set_ddl")],
            [InlineKeyboardButton(f"{'✅' if 'rating' in post_data[user_id]['data'] else ''} Rating", 
                                callback_data="set_rating")],
            [InlineKeyboardButton(f"{'✅' if 'description' in post_data[user_id]['data'] else ''} Description", 
                                callback_data="set_description")],
            [InlineKeyboardButton(f"{'✅' if 'episode' in post_data[user_id]['data'] else ''} Episode Number", 
                                callback_data="set_episode")],
            [InlineKeyboardButton(f"{'✅' if 'cover' in post_data[user_id]['data'] else ''} Cover Image URL", 
                                callback_data="set_cover")],
            [InlineKeyboardButton(f"{'✅' if 'genres' in post_data[user_id]['data'] else ''} Genres", 
                                callback_data="set_genres")],
            [InlineKeyboardButton("✅ Create Post", callback_data="create_post")]
        ]

        await message.reply(
            "🎬 <b>Create New Post</b>\n\nPlease fill in the remaining details (Title and DDL are required):",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        logger.error(f"Input handling failed: {e}")
        await message.reply("An error occurred. Please try again with /post")