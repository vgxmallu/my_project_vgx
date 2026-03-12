from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
from vgx.database.spoty_db import get_settings, get_ready_groups, update_settings, add_to_delete_queue, get_expired_deletes, remove_from_queue

def build_spoti_kb(chat_id: int, s: dict):
    en_txt = "🟢 Module: ON" if s["enabled"] else "🔴 Module: OFF"
    pin_txt = "📌 Auto-Pin: ON" if s["pin"] else "📌 Auto-Pin: OFF"
    
    # Format Interval Text
    int_txt = f"⏱ Interval: {s['interval']}m" if s['interval'] < 60 else "⏱ Interval: 1h"
    
    # Format Delete Text
    del_txt = f"🗑 Auto-Delete: {s['auto_delete']}s" if s['auto_delete'] > 0 else "🗑 Auto-Delete: OFF"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(en_txt, callback_data=f"sp_tgl_{chat_id}")],
        [
            InlineKeyboardButton(int_txt, callback_data=f"sp_int_{chat_id}"),
            InlineKeyboardButton(del_txt, callback_data=f"sp_del_{chat_id}")
        ],
        [InlineKeyboardButton(pin_txt, callback_data=f"sp_pin_{chat_id}")]
    ])

@Client.on_message(filters.command("spotitarget") & filters.private)
async def target_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/spotitarget -100123456789`")
    try:
        chat_id = int(message.command[1])
        s = await get_settings(chat_id)
        await message.reply(
            f"🎧 **Spotify Drop Dashboard**\n🎯 **Target:** `{chat_id}`\nCustomize the schedule below:", 
            reply_markup=build_spoti_kb(chat_id, s)
        )
    except ValueError:
        await message.reply("❌ Invalid Group ID.")

@Client.on_callback_query(filters.regex(r"^sp_(?P<action>tgl|int|del|pin)_(?P<chat_id>-?\d+)$"))
async def spoti_ui_router(client, query):
    action = query.matches[0].group("action")
    chat_id = int(query.matches[0].group("chat_id"))
    s = await get_settings(chat_id)
    
    if action == "tgl":
        # If turning on, reset the timer to start right now
        updates = {"enabled": not s["enabled"]}
        if not s["enabled"]: 
            updates["next_send_time"] = datetime.utcnow()
        await update_settings(chat_id, **updates)
        
    elif action == "pin":
        await update_settings(chat_id, pin=not s["pin"])
        
    elif action == "int":
        intervals = [1, 5, 20, 30, 60]
        nxt = intervals[(intervals.index(s["interval"]) + 1) % len(intervals)] if s["interval"] in intervals else 60
        await update_settings(chat_id, interval=nxt)
        
    elif action == "del":
        deletes = [0, 30, 300, 400, 2400]
        nxt = deletes[(deletes.index(s["auto_delete"]) + 1) % len(deletes)] if s["auto_delete"] in deletes else 0
        await update_settings(chat_id, auto_delete=nxt)

    s = await get_settings(chat_id)
    await query.message.edit_reply_markup(reply_markup=build_spoti_kb(chat_id, s))


import asyncio
import random
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from datetime import datetime, timedelta
from config import Config

auth_manager = SpotifyClientCredentials(client_id=Config.SPOTIPY_CLIENT_ID, client_secret=Config.SPOTIPY_CLIENT_SECRET)
sp = spotipy.Spotify(auth_manager=auth_manager)

def get_full_spotify_track():
    """Fetches rich metadata for a truly random track."""
    wildcards = ['%a%', '%e%', '%i%', '%o%', '%u%']
    query = random.choice(wildcards)
    offset = random.randint(0, 900)
    
    try:
        # Pull 50 tracks at once to guarantee we find a good one
        results = sp.search(q=query, type='track', limit=50, offset=offset)
        tracks = results['tracks']['items']
        
        if not tracks:
            return None
            
        track = random.choice(tracks) # Pick one random track from the 50
        
        # Format multiple artists neatly
        artists = ", ".join([artist['name'] for artist in track['artists']])
        
        return {
            "name": track['name'],
            "artist": artists,
            "album": track['album']['name'],
            "release_date": track['album']['release_date'],
            "popularity": track['popularity'],
            "url": track['external_urls']['spotify'],
            "preview_url": track['preview_url'], # This is a direct MP3 link (can be None)
            "image": track['album']['images'][0]['url'] if track['album']['images'] else None
        }
    except Exception as e:
        print(f"Spotify Fetch Error: {e}")
        return None

# --- Loop 1: The Music Sender ---
async def drop_sender_loop(app):
    while True:
        try:
            now = datetime.utcnow()
            
            # Only fetch groups where next_send_time has been reached
            groups = await get_ready_groups(now)
            
            for group in groups:
                chat_id = group["chat_id"]
                track = get_full_spotify_track()
                
                if track:
                    # Building the "Full Information" layout
                    preview_txt = f"\n🔊 [Play 30s Audio Preview]({track['preview_url']})" if track['preview_url'] else ""
                    
                    caption = (
                        "🎧 **Spotify Discovery Drop** 🎧\n"
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        f"🎵 **Track:** {track['name']}\n"
                        f"🎤 **Artist:** {track['artist']}\n"
                        f"💿 **Album:** {track['album']}\n"
                        f"📅 **Released:** {track['release_date']}\n"
                        f"📈 **Popularity Score:** {track['popularity']}/100\n"
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        f"🔗 [Open in Spotify]({track['url']}){preview_txt}"
                    )
                    
                    try:
                        # 1. Send the message
                        if track["image"]:
                            msg = await app.send_photo(chat_id, photo=track["image"], caption=caption)
                        else:
                            msg = await app.send_message(chat_id, caption, disable_web_page_preview=False)
                            
                        # 2. Auto-Pin Logic
                        if group.get("pin"):
                            try:
                                await msg.pin(disable_notification=False)
                            except Exception:
                                pass 
                                
                        # 3. Auto-Delete Queue Logic
                        del_seconds = group.get("auto_delete", 0)
                        if del_seconds > 0:
                            await add_to_delete_queue(chat_id, msg.id, del_seconds)
                            
                        # 4. Schedule the NEXT drop based on their custom interval!
                        next_time = now + timedelta(minutes=group["interval"])
                        await update_settings(chat_id, next_send_time=next_time)
                        
                    except Exception as e:
                        print(f"Failed to send to {chat_id}: {e}")
                        
        except Exception as e:
            print(f"Sender Loop Error: {e}")
            
        await asyncio.sleep(15) # Check every 15 seconds

# --- Loop 2: The Auto-Delete Janitor ---
async def auto_delete_loop(app):
    while True:
        try:
            now = datetime.utcnow()
            expired_tasks = await get_expired_deletes(now)
            
            for task in expired_tasks:
                try:
                    await app.delete_messages(task["chat_id"], task["message_id"])
                except Exception:
                    pass 
                
                # Delete from DB queue so we don't try again
                await remove_from_queue(task["_id"])
                
        except Exception as e:
            print(f"Janitor Loop Error: {e}")
            
        await asyncio.sleep(10) # Sweep the queue every 10 seconds
           
