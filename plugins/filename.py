import re
import logging

logger = logging.getLogger(__name__)

def convert_filename(original_name):
    try:
        # Remove file extension(s)
        name = re.sub(r'\.mkv\.mkv$', '', original_name)  # Handle double .mkv
        name = re.sub(r'\.(mkv|mp4)$', '', name)  # Remove extension
        
        # Extract episode number first
        number_match = re.search(r'\[(\d+)\]', name)
        episode_num = None
        if number_match:
            episode_num = number_match.group(1)
            
        # Replace [Sub] with [Eng Sub]
        name = re.sub(r'\[Sub\]', '[Eng Sub]', name, flags=re.IGNORECASE)
        
        # Replace @donghuafirst with @HeavenlySubs
        name = re.sub(r'@\w+', '@HeavenlySubs', name)
        
        # Format the final name with episode number
        if episode_num:
            # Keep the episode number in brackets format
            return f"[{episode_num}]{name.replace(f'[{episode_num}]', '')}"
        return name
        
    except Exception as e:
        logger.error(f"Error converting filename: {e}")
        return original_name