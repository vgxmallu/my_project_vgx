import os
import time
import subprocess
from config import Config

import shutil
from pyrogram import Client, filters
from pyrogram.types import Message

def download_spotify_track(url: str):
    """
    Uses spotdl to match the Spotify track to YouTube Music,
    download the MP3, and apply the Spotify cover art and ID3 tags.
    """
    # Create a unique temporary folder for this download
    task_id = str(int(time.time()))
    task_dir = os.path.join(Config.DOWNLOAD_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    try:
        # Run the spotdl command line tool via subprocess
        # This downloads the song and names it "Title - Artist.mp3"
        process = subprocess.run(
            ["spotdl", "download", url, "--output", f"{task_dir}/{{title}} - {{artist}}.{{ext}}"],
            cwd=task_dir,
            capture_output=True,
            text=True
        )

        # Look for the resulting .mp3 file in our temporary folder
        for file in os.listdir(task_dir):
            if file.endswith(".mp3"):
                return os.path.join(task_dir, file), task_dir

        print(f"SpotDL Error: {process.stderr}")
        return None, task_dir
        
    except Exception as e:
        print(f"Spotify Download Exception: {e}")
        return None, task_dir





# Matches ONLY Spotify track links (no playlists/albums to prevent group spam)
SP_REGEX = r"(https?://open\.spotify\.com/track/[a-zA-Z0-9]+)"

# Listen in both private chats AND groups
@Client.on_message(filters.regex(SP_REGEX) & (filters.private | filters.group))
async def handle_spotify_link(client: Client, message: Message):
    url = message.matches[0].group(1)
    
    status_msg = await message.reply_text("🔎 **Searching for track...** (Applying cover art & metadata)")
    
    filepath, task_dir = download_spotify_track(url)
    
    if filepath and os.path.exists(filepath):
        await status_msg.edit_text("📤 **Uploading to Telegram...**")
        
        try:
            # Send the audio file. Pyrogram automatically reads the ID3 tags (cover art/artist)
            await message.reply_audio(
                audio=filepath, 
                caption="Here is your track! 🎵"
            )
        except Exception as e:
            await message.reply_text(f"❌ **Upload Failed:** {str(e)}")
        finally:
            # Clean up the unique folder
            shutil.rmtree(task_dir, ignore_errors=True)
            await status_msg.delete()
    else:
        shutil.rmtree(task_dir, ignore_errors=True)
        await status_msg.edit_text("❌ **Download Failed.** The track might not be available or the link is invalid.")
