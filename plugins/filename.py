import re
import logging

logger = logging.getLogger(__name__)

def convert_filename(original_name):
    """
    Converts original filename to new format
    Example: [142]Battle Through The Heavens[720p][Sub]@donghwa_first.mkv
    To: S5EP142 - Battle Through The Heavens @HeavenlySubs
    """
    try:
        # Extract episode number
        pattern = r'\[?(\d+)\]?.*?Battle.*?Through.*?Heavens'
        match = re.search(pattern, original_name, re.IGNORECASE)
        
        if match:
            episode_num = match.group(1)
            return f"S5EP{episode_num} - Battle Through The Heavens @HeavenlySubs"
        
        # Fallback pattern
        number_match = re.search(r'(\d+)', original_name)
        if number_match:
            episode_num = number_match.group(1)
            return f"S5EP{episode_num} - Battle Through The Heavens @HeavenlySubs"
            
        return f"Battle Through The Heavens @HeavenlySubs"
    except Exception as e:
        logger.error(f"Error converting filename: {e}")
        return original_name