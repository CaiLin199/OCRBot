import os
import asyncio
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot import Bot
from config import OWNER_IDS, MAIN_CHANNEL, CHANNEL_ID, POST_FORMAT, THUMBNAIL
from datetime import datetime
from .shared_data import user_data, is_auto_mode, logger
from .link_generation import generate_link
from .downloader import download_file  # This will use aria2c

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

        # Progress callback for aria2c download
        async def progress_callback(current, total):
            nonlocal last_update_time
            now = datetime.now()
            
            if (now - last_update_time).seconds < 7:  # Update every 7 seconds
                return
                
            last_update_time = now
            progress_text = create_progress_text(current, total, start_time)
            
            try:
                await status_msg.edit(progress_text)
                await channel_msg.edit(progress_text)
            except Exception as e:
                if "420 FLOOD_WAIT" not in str(e):
                    logger.error(f"Progress update failed: {str(e)}")

        # Download file using aria2c
        file_path = await download_file(url, progress_callback)
        
        if file_path:
            # Upload to channel
            await upload_and_generate_link(client, file_path, message.from_user.id, status_msg, channel_msg)
        else:
            await status_msg.edit("❌ Download failed!")
            await channel_msg.delete()

    except Exception as e:
        logger.error(f"DDL processing failed: {e}")
        await message.reply(f"❌ Error: {str(e)}")
        if 'channel_msg' in locals():
            await channel_msg.delete()

@Bot.on_message(filters.command('post') & filters.user(OWNER_IDS))
async def handle_post(client, message):
    try:
        # Initialize post data
        user_id = message.from_user.id
        post_data[user_id] = {
            "step": "rating",
            "data": {}
        }

        # Create buttons for post creation
        buttons = [
            [InlineKeyboardButton("Rating", callback_data="set_rating")],
            [InlineKeyboardButton("Title", callback_data="set_title")],
            [InlineKeyboardButton("Description", callback_data="set_description")],
            [InlineKeyboardButton("Episode Number", callback_data="set_episode")],
            [InlineKeyboardButton("Cover Image URL", callback_data="set_cover")],
            [InlineKeyboardButton("Genres", callback_data="set_genres")],
            [InlineKeyboardButton("Direct Download Link", callback_data="set_ddl")],
            [InlineKeyboardButton("✅ Create Post", callback_data="create_post")]
        ]

        await message.reply(
            "🎬 <b>Create New Post</b>\n\nPlease fill in the following details:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        logger.error(f"Post creation failed: {e}")
        await message.reply(f"❌ Error: {str(e)}")

async def upload_and_generate_link(client, file_path, user_id, status_msg, channel_msg):
    try:
        # Update status
        await status_msg.edit("📤 Uploading to channel...")
        await channel_msg.edit("Status: Uploading to channel...")
        
        # Upload file to channel with progress
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

        # Upload file
        thumbnail = THUMBNAIL
        uploaded = await client.send_document(
            CHANNEL_ID,
            file_path,
            force_document=True,
            thumb=thumbnail,
            progress=upload_progress
        )

        # Generate shareable link
        share_link = await generate_link(client, uploaded.message_id)
        
        # Create post with generated link
        post_text = POST_FORMAT.format(
            title=post_data[user_id]['data'].get('title', ''),
            description=post_data[user_id]['data'].get('description', ''),
            rating=post_data[user_id]['data'].get('rating', '⭐️⭐️⭐️⭐️⭐️'),
            episode=post_data[user_id]['data'].get('episode', ''),
            genres=post_data[user_id]['data'].get('genres', ''),
            link=share_link
        )

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
    
    # Calculate speed and progress
    speed = current / diff if diff > 0 else 0
    percentage = current * 100 / total if total > 0 else 0
    
    # Calculate ETA
    if speed > 0:
        eta = (total - current) / speed
    else:
        eta = 0
    
    # Format time values
    eta_str = str(datetime.fromtimestamp(eta) - datetime.fromtimestamp(0))
    elapsed_time = str(datetime.fromtimestamp(diff) - datetime.fromtimestamp(0))
    
    # Create progress bar
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
            # Check if required fields are filled
            required_fields = ['title', 'description', 'ddl']
            missing_fields = [field for field in required_fields if field not in post_data[user_id]['data']]
            
            if missing_fields:
                return await callback_query.answer(
                    f"Please fill in required fields: {', '.join(missing_fields)}",
                    show_alert=True
                )

            # Start download and upload process
            await callback_query.message.edit_text("Starting download process...")
            await handle_ddl(client, post_data[user_id]['data']['ddl'])
            
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
        await callback_query.answer("An error occurred. Please try again.")

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
            [InlineKeyboardButton(f"✅ Rating" if 'rating' in post_data[user_id]['data'] else "Rating", 
                                callback_data="set_rating")],
            [InlineKeyboardButton(f"✅ Title" if 'title' in post_data[user_id]['data'] else "Title", 
                                callback_data="set_title")],
            [InlineKeyboardButton(f"✅ Description" if 'description' in post_data[user_id]['data'] else "Description", 
                                callback_data="set_description")],
            [InlineKeyboardButton(f"✅ Episode Number" if 'episode' in post_data[user_id]['data'] else "Episode Number", 
                                callback_data="set_episode")],
            [InlineKeyboardButton(f"✅ Cover Image URL" if 'cover' in post_data[user_id]['data'] else "Cover Image URL", 
                                callback_data="set_cover")],
            [InlineKeyboardButton(f"✅ Genres" if 'genres' in post_data[user_id]['data'] else "Genres", 
                                callback_data="set_genres")],
            [InlineKeyboardButton(f"✅ Direct Download Link" if 'ddl' in post_data[user_id]['data'] else "Direct Download Link", 
                                callback_data="set_ddl")],
            [InlineKeyboardButton("✅ Create Post", callback_data="create_post")]
        ]

        await message.reply(
            "🎬 <b>Create New Post</b>\n\nPlease fill in the remaining details:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        logger.error(f"Input handling failed: {e}")
        await message.reply("An error occurred. Please try again with /post")