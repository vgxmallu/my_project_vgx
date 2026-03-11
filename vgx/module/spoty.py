from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.spoty_db import get_spoti_settings, update_spoti_settings, get_all_enabled_groups
import asyncio
import random
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from datetime import datetime
from config import Config

def build_spoti_menu(chat_id: int, enabled: bool):
    btn_text = "🟢 Spotify Drop: ENABLED" if enabled else "🔴 Spotify Drop: DISABLED"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_text, callback_data=f"spoti_tgl_{chat_id}")]
    ])

@Client.on_message(filters.command("spotitarget") & filters.private)
async def spoti_target_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/spotitarget -100123456789`")
        
    try:
        chat_id = int(message.command[1])
        s = await get_spoti_settings(chat_id)
        
        text = (
            "🎧 **Spotify Music Drop Settings**\n\n"
            "This module will automatically fetch a random track from Spotify "
            "and share it with the group every 4 hours.\n\n"
            f"🎯 **Target Group:** `{chat_id}`"
        )
        await message.reply(text, reply_markup=build_spoti_menu(chat_id, s["enabled"]))
    except ValueError:
        await message.reply("❌ Please provide a valid numeric Group ID.")

@Client.on_callback_query(filters.regex(r"^spoti_tgl_(?P<chat_id>-?\d+)$"))
async def spoti_callbacks(client, query):
    chat_id = int(query.matches[0].group("chat_id"))
    s = await get_spoti_settings(chat_id)
    
    new_state = not s["enabled"]
    await update_spoti_settings(chat_id, enabled=new_state)
    
    # Refresh the UI smoothly
    await query.message.edit_reply_markup(reply_markup=build_spoti_menu(chat_id, new_state))
    await query.answer(f"Spotify Drop {'Enabled' if new_state else 'Disabled'}!", show_alert=True)

# Initialize Spotify API Client
auth_manager = SpotifyClientCredentials(
    client_id=Config.SPOTIPY_CLIENT_ID, 
    client_secret=Config.SPOTIPY_CLIENT_SECRET
)
sp = spotipy.Spotify(auth_manager=auth_manager)

def get_random_spotify_track():
    """Fetches a random track using randomized wildcards and offsets."""
    wildcards = ['%a%', '%e%', '%i%', '%o%', '%u%']
    random_wildcard = random.choice(wildcards)
    offset = random.randint(0, 1000) # Spotify allows an offset up to 1000
    
    try:
        results = sp.search(q=random_wildcard, type='track', limit=1, offset=offset)
        items = results['tracks']['items']
        
        if items:
            track = items[0]
            return {
                "name": track['name'],
                "artist": track['artists'][0]['name'],
                "album": track['album']['name'],
                "url": track['external_urls']['spotify'],
                "image": track['album']['images'][0]['url'] if track['album']['images'] else None
            }
    except Exception as e:
        print(f"Spotify API Error: {e}")
        
    return None

async def spotify_drop_loop(app):
    while True:
        try:
            now = datetime.utcnow()
            
            # TRIGGER: Runs every 4 hours exactly on the hour (e.g., 00:00, 04:00, 08:00, 12:00)
            if now.hour % 4 == 0 and now.minute == 0:
                groups = await get_all_enabled_groups()
                
                if groups:
                    track_info = get_random_spotify_track()
                    
                    if track_info:
                        # Build the beautiful message format
                        caption = (
                            "🎧 **Random Spotify Drop!** 🎧\n"
                            "━━━━━━━━━━━━━━━━━━━━\n"
                            f"🎵 **Track:** {track_info['name']}\n"
                            f"🎤 **Artist:** {track_info['artist']}\n"
                            f"💿 **Album:** {track_info['album']}\n"
                            "━━━━━━━━━━━━━━━━━━━━\n"
                            f"🔗 [Listen on Spotify]({track_info['url']})"
                        )
                        
                        # Loop through your enabled groups and send the drop
                        for group in groups:
                            chat_id = group["chat_id"]
                            try:
                                if track_info["image"]:
                                    # Sends the Album Art as a photo with the text attached
                                    await app.send_photo(chat_id, photo=track_info["image"], caption=caption)
                                else:
                                    await app.send_message(chat_id, caption, disable_web_page_preview=False)
                            except Exception as e:
                                print(f"Failed to send Spotify drop to {chat_id}: {e}")
                                
                # Sleep for 60 seconds so it doesn't trigger multiple times in the same minute
                await asyncio.sleep(60)
                
        except Exception as e:
            print(f"Spotify Scheduler Error: {e}")
            
        await asyncio.sleep(20) # Normal background check interval
