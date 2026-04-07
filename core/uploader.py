import os
import asyncio
from db.local_db import add_file

async def upload_file_to_telegram(file_path, progress_callback=None, override_type=None):
    from cloud_auth.login import get_client

    client = get_client()
    if not client.is_connected():
        await client.connect()
        
    print(f"Uploading {file_path} to Telegram...")
    message = await client.send_file('me', file_path, progress_callback=progress_callback)
    
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    ext = os.path.splitext(file_name)[1].lower()
    
    if override_type:
        file_type = override_type
    elif ext in ['.png', '.jpg', '.jpeg', '.gif']: file_type = 'image'
    elif ext in ['.mp4', '.avi', '.mkv']: file_type = 'video'
    else: file_type = 'document'
    
    add_file(message.id, file_name, file_size, file_type)
    return message
