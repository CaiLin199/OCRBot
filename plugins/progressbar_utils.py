import time
import sys

# design progressbar 

def progressbar(status_msg, total_size_mb, downloaded_mb, speed_mbps):
    
    num_bars = 10 # number of total bars in progressbarr
    
    percent = downloaded_mb / total_size_mb
    filled_bars = int(percent * num_bars)
    unfilled_bars = num_bars - filled_bars
    
    progress_bar = ('■' * filled_bars) + ('□' * unfilled_bars)
    
    #progress_bar format
    
    prog_msg = (
        f"{status_msg}\n"
        f"{progress_bar}\n"
        f"{downloaded_mb:.2f} MB / {total_size_mb:.2f}\n"
        f"Speed: {speed_mbps:.2f} MB/s\n"
    )
    return prog_msg