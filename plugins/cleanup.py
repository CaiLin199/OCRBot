import os
import logging

def cleanup(user_id):
    from .video_handler import user_data  # Import here to avoid circular import
    if user_id in user_data:
        data = user_data[user_id]
        for key in ["video", "subtitle"]:
            if key in data and os.path.exists(data[key]):
                os.remove(data[key])
        user_data.pop(user_id, None)
        logging.info(f"Cleaned up data for user {user_id}")
