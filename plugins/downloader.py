#donot use this code commented out

'''
import os
import asyncio
from .shared_data import logger

async def download_file(url, progress_callback):
    try:
        # Create download directory if not exists
        download_dir = "downloads"
        os.makedirs(download_dir, exist_ok=True)

        # Prepare aria2c command
        cmd = [
            "aria2c",
            "--max-connection-per-server=16",
            "--min-split-size=1M",
            "--split=16",
            "--max-concurrent-downloads=1",
            "--file-allocation=none",
            "--dir=" + download_dir,
            url
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Monitor download progress
        file_size = 0
        downloaded = 0
        while True:
            if process.stdout is None:
                continue

            line = await process.stdout.readline()
            if not line:
                break

            line = line.decode().strip()
            
            # Parse file size
            if "Length:" in line:
                try:
                    file_size = int(line.split()[1].strip("()"))
                except:
                    pass
                
            # Parse progress
            elif "[#" in line:
                try:
                    downloaded = int(line.split()[1].split("/")[0])
                    if file_size > 0:
                        await progress_callback(downloaded, file_size)
                except:
                    pass

        await process.wait()
        
        # Find downloaded file
        for file in os.listdir(download_dir):
            if not file.endswith(".aria2"):
                file_path = os.path.join(download_dir, file)
                return file_path

        return None

    except Exception as e:
        logger.error(f"Download failed: {e}")
        return None

'''