import re
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

def process_subtitle(input_file, output_file):
    """
    Process ASS subtitle file according to specified requirements.
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        processed_lines = []
        in_events = False
        found_episode = False
        skip_until_episode = True
        episode_number = None

        # Process line by line
        for line in lines:
            # Handle style section - replace Arial with Oath-Bold and size 16 with 20
            if line.startswith('Style: Default,Arial,16,'):
                line = line.replace('Arial,16,', 'Oath-Bold,20,')
                processed_lines.append(line)
                continue

            # Detect Events section
            if line.strip() == '[Events]':
                in_events = True
                processed_lines.append(line)
                continue

            # Process Events section
            if in_events and line.startswith('Dialogue:'):
                # Extract episode number if not found yet
                if not found_episode:
                    episode_match = re.search(r'Episode:?\s*(\d+)', line, re.IGNORECASE)
                    if episode_match:
                        episode_number = episode_match.group(1)
                        found_episode = True
                        skip_until_episode = False
                        # Replace with new format
                        new_line = f'Dialogue: 0,{line.split(",", 4)[1]},Default,,0,0,0,,Episode {episode_number} - [HeavenlySubs]\n'
                        processed_lines.append(new_line)
                        continue

                # Skip lines before episode
                if skip_until_episode:
                    continue

                # Skip "Next Episode" line
                if 'Next Episode' in line:
                    continue

                # Include other dialogue lines after episode
                if not skip_until_episode:
                    processed_lines.append(line)
                    
            else:
                # Include non-dialogue lines
                processed_lines.append(line)

        # Write processed content
        with open(output_file, 'w', encoding='utf-8') as f:
            f.writelines(processed_lines)

        logger.info(f"Successfully processed subtitle: {input_file} -> {output_file}")
        return True, f"Episode {episode_number}" if episode_number else "Unknown Episode"

    except Exception as e:
        logger.error(f"Error processing subtitle: {str(e)}")
        return False, str(e)

async def handle_subtitle(client, message, user_id):
    """
    Handle subtitle file upload and processing.
    """
    try:
        if not message.document or not message.document.file_name.endswith('.ass'):
            await message.reply("Please send an ASS subtitle file.")
            return

        file_name = message.document.file_name
        input_path = f"downloads/{file_name}"
        output_path = f"processed_{file_name}"

        # Download the subtitle file
        await message.download(file_name=input_path)

        # Process the subtitle
        success, info = process_subtitle(input_path, output_path)

        if success:
            from .video_handler import user_data
            if user_id not in user_data:
                user_data[user_id] = {}

            user_data[user_id]["subtitle"] = output_path
            user_data[user_id]["step"] = "subtitle"
            user_data[user_id]["caption"] = info

            await message.reply(
                f"✅ Subtitle processed successfully!\n"
                f"📝 {info}\n"
                f"Now send me the new name for the output file (without extension)."
            )
        else:
            await message.reply(f"❌ Error processing subtitle: {info}")

    except Exception as e:
        logger.error(f"Error in handle_subtitle: {e}")
        await message.reply(f"❌ Error: {str(e)}")