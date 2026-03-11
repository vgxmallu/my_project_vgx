

import os
import yt_dlp
from config import Config

from pyrogram import Client, filters
from pyrogram.types import Message

def download_ig_media(url: str):
    """
    Downloads Instagram media using yt-dlp.
    Returns the filepath on success, or None on failure.
    """
    # Options for yt-dlp
    ydl_opts = {
        'outtmpl': f'{Config.DOWNLOAD_DIR}/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'cookiefile': 'cookies.txt', # Un-comment and provide a cookies.txt file for Stories/Private posts
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Safely get the downloaded file's path
            filepath = ydl.prepare_filename(info)
            
            # yt-dlp sometimes changes the extension (e.g., .webm to .mp4). 
            # We check if the expected file exists, or find the actual downloaded file.
            if os.path.exists(filepath):
                return filepath
            
            # Fallback: find the closest match in the directory if exact path fails
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            for file in os.listdir(Config.DOWNLOAD_DIR):
                if file.startswith(base_name):
                    return os.path.join(Config.DOWNLOAD_DIR, file)
                    
            return None
            
    except Exception as e:
        print(f"Download Error: {e}")
        return None

# Regex to catch Instagram URLs (p, reel, reels, tv)
IG_REGEX = r"(https?://(?:www\.)?instagram\.com/(?:p|reel|reels|tv)/[^\s]+)"

@Client.on_message(filters.regex(IG_REGEX) & filters.private)
async def handle_instagram_link(client: Client, message: Message):
    url = message.matches[0].group(1)
    
    # 1. Notify user that processing has started
    status_msg = await message.reply_text("⏳ **Downloading media...** Please wait.")
    
    # 2. Call the download utility
    filepath = download_ig_media(url)
    
    # 3. Handle the result
    if filepath and os.path.exists(filepath):
        await status_msg.edit_text("📤 **Uploading to Telegram...**")
        
        try:
            # Check if it's a video or a photo
            if filepath.endswith(('.mp4', '.webm', '.mkv')):
                await message.reply_video(video=filepath, caption="Here is your video! 🎬")
            else:
                await message.reply_photo(photo=filepath, caption="Here is your photo! 📸")
        except Exception as e:
            await message.reply_text(f"❌ **Upload Failed:** {str(e)}")
        finally:
            # 4. Clean up: Delete the local file to save server storage
            os.remove(filepath)
            await status_msg.delete()
    else:
        await status_msg.edit_text(
            "❌ **Download Failed.**\n"
            "This could be because the account is private, or it's an unsupported format (like a Story without cookies)."
        )
