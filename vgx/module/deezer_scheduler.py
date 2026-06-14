from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from datetime import datetime
from vgx.database.deezer_db import get_settings, get_ready_groups, update_settings
def build_deezer_kb(chat_id: int, s: dict):
    en_txt = "🟢 Module: ON" if s["enabled"] else "🔴 Module: OFF"
    pin_txt = "📌 Auto-Pin: ON" if s["pin"] else "📌 Auto-Pin: OFF"
    int_txt = f"⏱ Interval: {s['interval']}m" if s['interval'] < 60 else "⏱ Interval: 1h"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(en_txt, callback_data=f"dz_tgl_{chat_id}")],
        [InlineKeyboardButton(int_txt, callback_data=f"dz_int_{chat_id}")],
        [InlineKeyboardButton(pin_txt, callback_data=f"dz_pin_{chat_id}")]
    ])

@Client.on_message(filters.command("deezertarget") & filters.private)
async def targedeext_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/music_target -100123456789`")
    try:
        chat_id = int(message.command[1])
        s = await get_settings(chat_id)
        
        text = (
            f"🎧 **Deezer Music Dashboard**\n"
            f"🎯 **Target:** `{chat_id}`\n\n"
            f"Customize the schedule below:"
        )
        await message.reply(text, reply_markup=build_deezer_kb(chat_id, s))
    except ValueError:
        await message.reply("❌ Invalid Group ID.")

@Client.on_callback_query(filters.regex(r"^dz_(?P<action>tgl|int|pin)_(?P<chat_id>-?\d+)$"))
async def deezer_ui_router(client, query):
    action = query.matches[0].group("action")
    chat_id = int(query.matches[0].group("chat_id"))
    s = await get_settings(chat_id)
    
    if action == "tgl":
        updates = {"enabled": not s["enabled"]}
        # If turning ON, reset the timer so it drops a song immediately!
        if not s["enabled"]: 
            updates["next_send_time"] = datetime.utcnow()
        await update_settings(chat_id, **updates)
        
    elif action == "pin":
        await update_settings(chat_id, pin=not s["pin"])
        
    elif action == "int":
        # Cycle through your requested intervals: 1m -> 5m -> 20m -> 30m -> 60m
        intervals = [1, 5, 20, 30, 60]
        nxt = intervals[(intervals.index(s["interval"]) + 1) % len(intervals)] if s["interval"] in intervals else 60
        await update_settings(chat_id, interval=nxt)

    # Fetch fresh data and update the UI smoothly
    s = await get_settings(chat_id)
    await query.message.edit_reply_markup(reply_markup=build_deezer_kb(chat_id, s))

import asyncio
import random
import aiohttp
from datetime import datetime, timedelta

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
async def fetch_random_deezer_track():
    """Fetches a highly random track with full metadata from Deezer."""
    wildcards = ['phonk_brazil', 'edm', 'phonk', 'funk', 'dubstep', 'english']
    query = random.choice(wildcards)
    offset = random.randint(0, 1000) 
    
    url = f"https://api.deezer.com/search?q={query}&limit=50&index={offset}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    tracks = data.get('data', [])
                    
                    if not tracks:
                        return None
                        
                    track = random.choice(tracks)
                    
                    # Deezer rank goes up to a million, format with commas!
                    rank = f"{track.get('rank', 0):,}"
                    
                    return {
                        "name": track['title'],
                        "artist": track['artist']['name'],
                        "album": track['album']['title'],
                        "popularity": rank,
                        "url": track['link'],
                        "preview_url": track['preview'], 
                        "image": track['album']['cover_xl'] 
                    }
                return None
    except Exception as e:
        print(f"Deezer Fetch Error: {e}")
        return None
        
from pyrogram.enums import ButtonStyle


async def music_scheduler_loop(app):
    while True:
        try:
            now = datetime.utcnow()
            
            # Find groups that are due for a song RIGHT NOW
            groups = await get_ready_groups(now)
            
            for group in groups:
                chat_id = group["chat_id"]
                track = await fetch_random_deezer_track()
                
                if track:
                    # Build the "Full Information" layout
                    preview_txt = f"\n🔊 [Play 30s Audio Preview]({track['preview_url']})" if track['preview_url'] else ""
                    add_button = InlineKeyboardMarkup(
                        [[
                           InlineKeyboardButton("⛓️‍💥 Track Link", url=track['url'], style=ButtonStyle.PRIMARY)
                        ]] 
                    )
                    caption = (
                        "💜 **Music Discovery Drop** 💜\n"
                        "━━━━━━━━━━━━━\n"
                        f"🎵 **Track:** {track['name']}\n"
                        f"🎤 **Artist:** {track['artist']}\n"
                        f"💿 **Album:** {track['album']}\n"
                        f"📊 **Deezer Rank:** {track['popularity']}\n"
                        "━━━━━━━━━━━━━\n"
                        f"🔗 [Listen Full Track]({track['url']}){preview_txt}"
                    )
                    
                    try:
                        # 1. Send the Message
                        if track["image"]:
                            msg = await app.send_photo(chat_id, photo=track["image"], caption=caption, reply_markup=add_button)
                        else:
                            msg = await app.send_message(chat_id, caption, disable_web_page_preview=False, reply_markup=add_button)
                            
                        # 2. Auto-Pin if enabled
                        if group.get("pin"):
                            try:
                                await msg.pin(disable_notification=False)
                            except Exception:
                                pass # Ignores if bot lacks pin rights
                                
                        # 3. Schedule the NEXT drop based on the database interval
                        next_time = now + timedelta(minutes=group["interval"])
                        await update_settings(chat_id, next_send_time=next_time)
                        
                    except Exception as e:
                        print(f"Failed to send to {chat_id}: {e}")
                        
        except Exception as e:
            print(f"Scheduler Loop Error: {e}")
            
        await asyncio.sleep(15) # Check the database every 15 seconds

