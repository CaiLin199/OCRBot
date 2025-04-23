from plugins.aria2_client import aria2

def add_download(url: str):
    try:
        download = aria2.add_uris([url])
        return f"Download added! GID: {download.gid}"
    except Exception as e:
        return f"Failed to add download: {e}"