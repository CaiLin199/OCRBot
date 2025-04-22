import base64
from config import CHANNEL_ID

async def encode(string):
    """Encode a string to base64."""
    string_bytes = string.encode('ascii')
    base64_bytes = base64.urlsafe_b64encode(string_bytes)
    base64_string = base64_bytes.decode('ascii')
    return base64_string

# Fixed: Removed the unused client parameter
async def generate_link(message, user_data=None):  # Added optional parameter but we don't use it
    """Generate shareable link for a file message."""
    try:
        msg_id = message.id
        base64_string = await encode(f"get-{msg_id * abs(CHANNEL_ID)}")
        link = f"https://t.me/HeavenlySubsBot?start={base64_string}"
        return link
    except Exception as e:
        print(f"Error generating link: {e}")
        return None