import os
import yt_dlp
from config import Config

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

def download_youtube(url: str, format_type: str = "video"):
    """
    Downloads YouTube videos or audio.
    Automatically uses cookies.txt if it exists in the root directory.
    """
    ydl_opts = {
        'outtmpl': f'{Config.DOWNLOAD_DIR}/%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True,
    }

    # IMPORTANT: Automatically use cookies if the file exists!
    if os.path.exists("cookies_yt.txt"):
        ydl_opts['cookiefile'] = 'cookies_yt.txt'

    if format_type == "audio":
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
            
            # yt-dlp changes the extension to .mp3 after processing audio
            if format_type == "audio":
                filepath = os.path.splitext(filepath)[0] + '.mp3'
                
            if os.path.exists(filepath):
                return filepath
            return None
            
    except Exception as e:
        print(f"Download Error: {e}")
        return None



YT_REGEX = r"(https?://(?:www\.)?(?:youtube\.com|youtu\.be)/(?:watch\?v=|shorts/|)[^\s]+)"

# Dictionary to temporarily store the URL so the callback buttons know what to download
user_requests = {}

@Client.on_message(filters.regex(YT_REGEX) & filters.private)
async def handle_youtube_link(client: Client, message: Message):
    url = message.matches[0].group(1)
    user_requests[message.chat.id] = url
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎥 Download Video", callback_data="dl_video")],
        [InlineKeyboardButton("🎵 Download Audio (MP3)", callback_data="dl_audio")]
    ])
    
    await message.reply_text("What format would you like to download?", reply_markup=keyboard)

@Client.on_callback_query(filters.regex(r"^dl_(video|audio)$"))
async def youtube_format_callback(client: Client, query: CallbackQuery):
    chat_id = query.message.chat.id
    
    if chat_id not in user_requests:
        return await query.answer("Session expired. Please send the link again.", show_alert=True)
        
    url = user_requests[chat_id]
    format_type = query.matches[0].group(1)
    
    await query.message.edit_text(f"⏳ **Downloading {format_type}...** Please wait.")
    
    filepath = download_youtube(url, format_type)
    
    if filepath and os.path.exists(filepath):
        await query.message.edit_text(f"📤 **Uploading {format_type} to Telegram...**")
        
        try:
            if format_type == "video":
                await client.send_video(chat_id=chat_id, video=filepath, caption="Here is your video! 🎬")
            else:
                await client.send_audio(chat_id=chat_id, audio=filepath, caption="Here is your audio! 🎵")
        except Exception as e:
            await query.message.reply_text(f"❌ **Upload Failed:** {str(e)}\n\n*Note: Telegram bots have a 50MB limit.*")
        finally:
            os.remove(filepath)
            await query.message.delete()
            del user_requests[chat_id] # Clean up memory
    else:
        await query.message.edit_text("❌ **Download Failed.** Please check the link or ensure your cookies.txt is valid.")
        if chat_id in user_requests:
            del user_requests[chat_id]
