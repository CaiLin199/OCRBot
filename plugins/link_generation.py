import base64
from config import CHANNEL_ID

async def encode(string):
    """Encode a string to base64."""
    string_bytes = string.encode('ascii')
    base64_bytes = base64.urlsafe_b64encode(string_bytes)
    base64_string = base64_bytes.decode('ascii')
    return base64_string

async def generate_link(client, main_channel, message, user_data=None):
    """Generate shareable link for a file message."""
    try:
        msg_id = message.id
        # Use CHANNEL (or channel_id) in the encoding logic
        base64_string = await encode(f"get-{msg_id * abs(channel_id)}")
        link = f"https://t.me/HeavenlySubsBot?start={base64_string}"
        return link
    except Exception as e:
        print(f"Error generating link: {e}")
        return None