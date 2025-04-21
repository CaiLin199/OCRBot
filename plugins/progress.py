from datetime import datetime

class Progress:
    def __init__(self, client, status_msg, channel_msg, action=""):
        self.client = client
        self.status_msg = status_msg
        self.channel_msg = channel_msg
        self.start_time = datetime.now()
        self.last_update_time = datetime.now()
        self.action = action
        
    def get_progress_bar(self, current, total):
        bar_length = 10  # Fixed length of 10 blocks
        if total == 0:
            percentage = 0
        else:
            percentage = current * 100 / total
        filled_length = int(percentage * bar_length / 100)
        bar = '■' * filled_length + '□' * (bar_length - filled_length)
        return bar, percentage
        
    def get_human_bytes(self, size):
        if not size:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        index = 0
        while size >= 1024.0 and index < len(units) - 1:
            size /= 1024.0
            index += 1
            
        return f"{size:.2f} {units[index]}"
        
    def get_time_stats(self, current, total, speed):
        if speed > 0:
            eta = (total - current) / speed
        else:
            eta = 0
            
        now = datetime.now()
        diff = (now - self.start_time).seconds
        
        eta_str = str(datetime.fromtimestamp(eta) - datetime.fromtimestamp(0))
        elapsed_time = str(datetime.fromtimestamp(diff) - datetime.fromtimestamp(0))
        
        return eta_str, elapsed_time
    
    async def update_progress(self, current, total):
        now = datetime.now()
        if (now - self.last_update_time).seconds < 7:  # Update every 7 seconds
            return
            
        self.last_update_time = now
        
        # Calculate speed
        diff = (now - self.start_time).seconds
        speed = current / diff if diff > 0 else 0
        
        # Get progress components
        bar, percentage = self.get_progress_bar(current, total)
        eta_str, elapsed_time = self.get_time_stats(current, total, speed)
        
        # Create progress text
        progress_text = (
            f"{self.action}\n"
            f"Progress: {bar} {percentage:.1f}%\n"
            f"Size: {self.get_human_bytes(current)} / {self.get_human_bytes(total)}\n"
            f"Speed: {self.get_human_bytes(speed)}/s\n"
            f"ETA: {eta_str}\n"
            f"Elapsed: {elapsed_time}"
        )
        
        try:
            await self.status_msg.edit(f"{progress_text}")
            await self.channel_msg.edit(f"Status: {progress_text}")
        except Exception as e:
            if "420 FLOOD_WAIT" not in str(e):
                logger.error(f"Progress update failed: {str(e)}")