from cloud_auth.login import get_client

async def download_file_from_telegram(message_id, dest_path, progress_callback=None, is_thumbnail=False):
    client = get_client()
    if not client.is_connected():
        await client.connect()

    message = await client.get_messages('me', ids=message_id)
    if message and message.media:
        if is_thumbnail:
            await client.download_media(message, dest_path, thumb=-1)
            return True
        else:
            print(f"Downloading file to {dest_path}...")
            await client.download_media(message, dest_path, progress_callback=progress_callback)
            return True
    return False
