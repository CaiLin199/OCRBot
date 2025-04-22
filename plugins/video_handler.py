import os
import asyncio
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from bot import Bot
from config import OWNER_ID, MAIN_CHANNEL
from datetime import datetime
from .shared_data import logger
from .post_handler import PostHandler
from .upload_handler import UploadHandler
from .progress import Progress
from .aria2_client import aria2

# Initialize handlers
post_handler = PostHandler()

class VideoHandler:
    def __init__(self):
        logger.info("VideoHandler initialized")
        
    async def _handle_ddl(self, client, message, url=None, user_id=None):
        """Handle DDL command and process downloads"""
        try:
            # Determine URL and user_id based on input
            if isinstance(message, Message):
                if not url and len(message.command) < 2:
                    return await message.reply("Please provide a direct download link!\nUsage: /ddl <url>")
                download_url = url or message.command[1]
                user_id = message.from_user.id
                status_msg = await message.reply("📥 Starting Download...")
            else:
                if not url:
                    return
                download_url = url
                status_msg = await message.edit_text("📥 Starting Download...")

            # Create channel message
            channel_msg = await client.send_message(
                MAIN_CHANNEL,
                "Status: Starting download..."
            )

            # Create progress tracker
            progress = Progress(client, status_msg, channel_msg, "📥 Downloading...")

            try:
                # Add download to aria2
                download = aria2.add_uris([download_url])
                file_path = None
                last_update_time = 0
                update_interval = 3  # Update every 3 seconds

                while not download.is_complete:
                    download.update()
                    current = download.completed_length
                    total = download.total_length
                    
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_update_time >= update_interval:
                        if total > 0:  # Prevent division by zero
                            percentage = (current * 100) / total
                            speed = download.download_speed
                            
                            # Format size
                            downloaded = current / (1024 * 1024)  # Convert to MB
                            total_size = total / (1024 * 1024)    # Convert to MB
                            
                            # Format speed
                            if speed > 1024*1024:  # MB/s
                                speed_text = f"{speed/(1024*1024):.1f} MB/s"
                            else:  # KB/s
                                speed_text = f"{speed/1024:.1f} KB/s"
                            
                            status_text = (
                                f"📥 Downloading... {percentage:.1f}%\n"
                                f"⚡️ Speed: {speed_text}\n"
                                f"📊 Size: {downloaded:.1f}MB / {total_size:.1f}MB"
                            )
                            await progress.update_progress(current, total, status_text)
                            last_update_time = current_time
                    
                    await asyncio.sleep(0.1)  # Reduced sleep time for better responsiveness

                if download.is_complete:
                    file_path = download.files[0].path
                    
                if file_path and os.path.exists(file_path):
                    await status_msg.edit_text("✅ Download Complete! Starting Upload...")
                    
                    # Get user's post data
                    post_data = post_handler.get_post_data(user_id)
                    
                    # Create upload handler and process upload
                    upload_handler = UploadHandler(
                        client, 
                        user_id, 
                        status_msg, 
                        channel_msg,
                        post_data
                    )
                    
                    # Upload file
                    msg_id = await upload_handler.upload_file(file_path)
                    
                    if msg_id:
                        # Generate shareable link
                        from .link_generation import generate_link
                        share_link = await generate_link(client, MAIN_CHANNEL, msg_id)
                        
                        if share_link:
                            # Send success message to user
                            await status_msg.edit_text(f"✅ Upload Complete!\n\n🔗 Share Link: {share_link}")
                            
                            # Create post in main channel
                            keyboard = [[InlineKeyboardButton("🎥 Watch Now", url=share_link)]]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            
                            try:
                                if post_data and post_data.get('cover_url'):
                                    # Send post with cover image
                                    await client.send_photo(
                                        chat_id=MAIN_CHANNEL,
                                        photo=post_data['cover_url'],
                                        caption=post_handler.format_post(post_data),
                                        reply_markup=reply_markup
                                    )
                                else:
                                    # Send post without cover image
                                    await client.send_message(
                                        chat_id=MAIN_CHANNEL,
                                        text=post_handler.format_post(post_data) if post_data else "✅ File Uploaded",
                                        reply_markup=reply_markup
                                    )
                            except Exception as e:
                                logger.error(f"Failed to send post: {e}")
                                await client.send_message(
                                    chat_id=MAIN_CHANNEL,
                                    text=post_handler.format_post(post_data) if post_data else "✅ File Uploaded",
                                    reply_markup=reply_markup
                                )
                    
                    # Clear post data after successful upload
                    if user_id:
                        post_handler.clear_post_data(user_id)
                    
                    # Clean up downloaded file
                    try:
                        os.remove(file_path)
                    except:
                        pass
                        
                else:
                    await status_msg.edit_text("❌ Download failed!")
                    await channel_msg.delete()

            except Exception as e:
                error_msg = str(e)
                if "not found" in error_msg.lower():
                    error_msg = "File not found. Please check the URL and try again."
                elif "access denied" in error_msg.lower():
                    error_msg = "Access denied. Please check if the link is accessible."
                    
                logger.error(f"Download failed: {e}")
                await status_msg.edit_text(f"❌ Download failed: {error_msg}")
                if 'channel_msg' in locals():
                    await channel_msg.delete()

        except Exception as e:
            logger.error(f"DDL processing failed: {e}")
            if isinstance(message, Message):
                await message.reply(f"❌ Error: {str(e)}")
            else:
                await message.edit_text(f"❌ Error: {str(e)}")
            if 'channel_msg' in locals():
                await channel_msg.delete()

# Create handler instance
video_handler = VideoHandler()

# Command handlers
@Bot.on_message(filters.command(['start', 'help']))
async def start_command(client, message):
    """Handle start and help commands"""
    if message.from_user.id != OWNER_ID:
        return await message.reply("Sorry, you are not authorized to use this bot.")
    
    help_text = """
🤖 **Available Commands**:

/start - Show this help message
/help - Show this help message
/post - Create a new post with metadata
/ddl <url> - Download and process a direct link

**Post Creation Process**:
1. Use /post to start
2. Fill in the required metadata
3. Add the direct download link
4. Click CREATE POST
"""
    await message.reply(help_text)

@Bot.on_message(filters.command('ddl') & filters.user(OWNER_ID))
async def handle_ddl(client, message):
    """Handle direct download link command"""
    await video_handler._handle_ddl(client, message)

@Bot.on_message(filters.command('post') & filters.user(OWNER_ID))
async def handle_post(client, message):
    """Handle post creation command"""
    await post_handler.handle_post_command(client, message)

@Bot.on_callback_query()
async def handle_callbacks(client, callback_query):
    """Handle callback queries"""
    try:
        if callback_query.data == "create_post":
            post_data = post_handler.get_post_data(callback_query.from_user.id)
            if not post_data.get('ddl'):
                await callback_query.answer("Direct Link is required!", show_alert=True)
                return
            
            await video_handler._handle_ddl(
                client,
                callback_query.message,
                url=post_data['ddl'],
                user_id=callback_query.from_user.id
            )
        else:
            await post_handler.handle_callback(client, callback_query)
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await callback_query.answer("An error occurred", show_alert=True)

@Bot.on_message(filters.private & filters.user(OWNER_ID))
async def handle_post_input(client, message):
    """Handle post input in private chat"""
    await post_handler.handle_input(client, message)