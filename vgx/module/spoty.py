import os
import time
import asyncio
from config import Config


import shutil

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait

async def download_spotify_media(url: str):
    """
    Asynchronously downloads a Track, Playlist, Album, or Artist.
    Returns a list of downloaded .mp3 file paths and the temporary directory.
    """
    task_id = str(int(time.time()))
    task_dir = os.path.join(Config.DOWNLOAD_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    # Base spotdl command
    # We output them sequentially with an autonumber if it's a playlist
    cmd = [
        "spotdl", "download", url, 
        "--output", f"{task_dir}/{{list-position}} - {{title}} - {{artist}}.{{ext}}"
    ]

    # Advanced: Automatically inject YouTube Music cookies if the file exists
    if os.path.exists("cookies.txt"):
        cmd.extend(["--cookie-file", "cookies.txt"])

    try:
        # Run process asynchronously to prevent bot from freezing
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=task_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        # Gather all downloaded mp3 files in the task directory
        downloaded_files = []
        for file in sorted(os.listdir(task_dir)):
            if file.endswith(".mp3"):
                downloaded_files.append(os.path.join(task_dir, file))
                
        return downloaded_files, task_dir
        
    except Exception as e:
        print(f"Async SpotDL Error: {e}")
        return [], task_dir



# Matches Track, Album, Playlist, and Artist links
SP_REGEX = r"(https?://open\.spotify\.com/(track|album|playlist|artist)/[a-zA-Z0-9]+)"

@Client.on_message(filters.regex(SP_REGEX) & (filters.private | filters.group))
async def handle_spotify_link(client: Client, message: Message):
    url = message.matches[0].group(1)
    media_type = message.matches[0].group(2).capitalize()
    
    status_msg = await message.reply_text(f"⏳ **Processing {media_type}...**\n*(Playlists and Albums may take a while! You can still use the bot for other things.)*")
    
    filepaths, task_dir = await download_spotify_media(url)
    
    if filepaths:
        await status_msg.edit_text(f"📤 **Uploading {len(filepaths)} track(s) to Telegram...**")
        
        success_count = 0
        for file in filepaths:
            try:
                # Upload the audio file
                await message.reply_audio(audio=file)
                success_count += 1
                
                # Small sleep to prevent Telegram from flagging the bot for spam
                await asyncio.sleep(1.5) 
                
            except FloodWait as e:
                # If Telegram says "You are uploading too fast", wait the required time and try again
                print(f"Hit FloodWait! Sleeping for {e.value} seconds...")
                await asyncio.sleep(e.value + 2)
                await message.reply_audio(audio=file)
                success_count += 1
                
            except Exception as e:
                print(f"Failed to upload one track: {e}")
                
        await status_msg.edit_text(f"✅ **Successfully uploaded {success_count}/{len(filepaths)} tracks!**")
        
    else:
        await status_msg.edit_text("❌ **Download Failed.**\nThe playlist might be private, empty, or age-restricted (if cookies are missing).")
        
    # Clean up the folder to save server space
    shutil.rmtree(task_dir, ignore_errors=True)
