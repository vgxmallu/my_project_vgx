from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import asyncio
import random
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from datetime import datetime, timedelta
from config import Config
from vgx.database.spoty_db import get_settings, get_active_groups, update_settings, add_to_delete_queue, get_expired_deletes, remove_from_queue



def build_spoti_kb(chat_id: int, s: dict):
    # Dynamic text formatting
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
        
        text = f"🎧 **Spotify Drop Dashboard**\n🎯 **Target:** `{chat_id}`\nCustomize your schedule below:"
        await message.reply(text, reply_markup=build_spoti_kb(chat_id, s))
    except ValueError:
        await message.reply("❌ Invalid Group ID.")

@Client.on_callback_query(filters.regex(r"^sp_(?P<action>tgl|int|del|pin)_(?P<chat_id>-?\d+)$"))
async def spoti_ui_router(client, query):
    action = query.matches[0].group("action")
    chat_id = int(query.matches[0].group("chat_id"))
    s = await get_settings(chat_id)
    
    if action == "tgl":
        await update_settings(chat_id, enabled=not s["enabled"])
        
    elif action == "pin":
        await update_settings(chat_id, pin=not s["pin"])
        
    elif action == "int":
        # Cycle through: 1 -> 5 -> 20 -> 30 -> 60
        intervals = [1, 5, 20, 30, 60]
        nxt = intervals[(intervals.index(s["interval"]) + 1) % len(intervals)] if s["interval"] in intervals else 60
        await update_settings(chat_id, interval=nxt)
        
    elif action == "del":
        # Cycle through: 0 -> 30 -> 300 -> 400 -> 2400
        deletes = [0, 30, 300, 400, 2400]
        nxt = deletes[(deletes.index(s["auto_delete"]) + 1) % len(deletes)] if s["auto_delete"] in deletes else 0
        await update_settings(chat_id, auto_delete=nxt)

    # Refresh DB and UI
    s = await get_settings(chat_id)
    await query.message.edit_reply_markup(reply_markup=build_spoti_kb(chat_id, s))



auth_manager = SpotifyClientCredentials(client_id=Config.SPOTIPY_CLIENT_ID, client_secret=Config.SPOTIPY_CLIENT_SECRET)
sp = spotipy.Spotify(auth_manager=auth_manager)

def get_spotify_track():
    try:
        results = sp.search(q=random.choice(['%a%', '%e%', '%i%', '%o%', '%u%']), type='track', limit=1, offset=random.randint(0, 900))
        track = results['tracks']['items'][0]
        return {
            "name": track['name'],
            "artist": track['artists'][0]['name'],
            "url": track['external_urls']['spotify'],
            "image": track['album']['images'][0]['url'] if track['album']['images'] else None
        }
    except Exception:
        return None

# --- Loop 1: The Music Sender ---
async def drop_sender_loop(app):
    while True:
        try:
            now = datetime.utcnow()
            groups = await get_active_groups()
            
            for group in groups:
                chat_id = group["chat_id"]
                last_sent = group.get("last_sent", now - timedelta(days=1))
                interval_mins = group.get("interval", 60)
                
                # Check if enough time has passed based on THEIR custom interval
                if now >= last_sent + timedelta(minutes=interval_mins):
                    track = get_spotify_track()
                    
                    if track:
                        caption = f"🎧 **Spotify Drop!**\n🎵 {track['name']}\n🎤 {track['artist']}\n🔗 [Listen Here]({track['url']})"
                        
                        try:
                            # 1. Send the message
                            if track["image"]:
                                msg = await app.send_photo(chat_id, photo=track["image"], caption=caption)
                            else:
                                msg = await app.send_message(chat_id, caption)
                                
                            # 2. Pin the message if enabled
                            if group.get("pin"):
                                try:
                                    await msg.pin(disable_notification=False)
                                except Exception:
                                    pass # Bot lacks admin pinning rights
                                    
                            # 3. Queue Auto-Delete if enabled
                            del_seconds = group.get("auto_delete", 0)
                            if del_seconds > 0:
                                await add_to_delete_queue(chat_id, msg.id, del_seconds)
                                
                            # 4. Update the last_sent timestamp
                            await update_settings(chat_id, last_sent=datetime.utcnow())
                            
                        except Exception as e:
                            print(f"Failed to send to {chat_id}: {e}")
                            
        except Exception as e:
            print(f"Sender Loop Error: {e}")
        await asyncio.sleep(20) # Check every 20 seconds

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
                    pass # Message was already deleted manually by an admin
                
                # Remove from database queue regardless of success
                await remove_from_queue(task["_id"])
                
        except Exception as e:
            print(f"Janitor Loop Error: {e}")
        await asyncio.sleep(10) # Sweep the queue every 10 seconds
