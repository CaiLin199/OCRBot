import re
import logging

logger = logging.getLogger(__name__)

def convert_filename(original_name):
    """
    Converts original filename to new format
    Example: [142]Battle Through The Heavens[720p][Sub]@donghwa_first.mkv
    To: 142 - Battle Through The Heavens @HeavenlySubs
    """
    try:
        # Remove file extension(s)
        name = re.sub(r'\.mkv\.mkv$', '', original_name)  # Handle double .mkv
        name = re.sub(r'\.(mkv|mp4)$', '', name)  # Remove extension
        
        # Remove quality tags and other unwanted patterns
        name = re.sub(r'\[720p\]|\[1080p\]|\[Sub\]|@\w+', '', name, flags=re.IGNORECASE)
        
        # Remove remaining brackets and their contents
        name = re.sub(r'\[.*?\]', '', name)
        
        # Extract episode number
        number_match = re.search(r'(\d+)', name)
        if number_match:
            episode_num = number_match.group(1)
            # Remove episode number from the name
            name = re.sub(r'^\[?\d+\]?', '', name)
            # Clean up the name
            name = name.strip(' -.')
            return f"{episode_num} - {name} @HeavenlySubs"
            
        # If no episode number found, just clean the name
        name = name.strip(' -.')
        return f"{name} @HeavenlySubs"
        
    except Exception as e:
        logger.error(f"Error converting filename: {e}")
        return original_name