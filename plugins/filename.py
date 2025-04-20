import re
import logging

logger = logging.getLogger(__name__)

def convert_filename(original_name):
    try:
        # Remove file extension(s)
        name = re.sub(r'\.mkv\.mkv$', '', original_name)  # Handle double .mkv
        name = re.sub(r'\.(mkv|mp4)$', '', name)  # Remove extension
        
        # Replace [Sub] with [Eng Sub]
        name = re.sub(r'\[Sub\]', '[Eng Sub]', name, flags=re.IGNORECASE)
        
        # Replace @donghuafirst with @HeavenlySubs
        name = re.sub(r'@\w+', '@HeavenlySubs', name)
        
        # Extract episode number and keep the formatting
        number_match = re.search(r'(\[?\d+\]?)', name)
        if number_match:
            return name
        return name
        
    except Exception as e:
        logger.error(f"Error converting filename: {e}")
        return original_name