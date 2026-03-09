import aiohttp
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.rsvp_event_db import create_master_event, get_event, update_event, get_user, alter_coins, events_col, add_strike
import random 
import asyncio
from pyrogram.types import ChatPermissions


def build_rsvp_keyboard(event_id: str, current: int, cap: int, cost: int):
    cost_txt = f" (💎 {cost})" if cost > 0 else " (Free)"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ Going {cost_txt} [{current}/{cap}]", callback_data=f"rsvp_yes_{event_id}")],
        [InlineKeyboardButton("❌ Cannot Go", callback_data=f"rsvp_no_{event_id}")],
        [InlineKeyboardButton("🌍 View in Local Time", url=f"https://t.me/YourBotName?start=time_{event_id}")]
    ])

# --- Watch Party Creator (AniList API) ---
@Client.on_message(filters.command("createwatchparty") & filters.group)
async def create_watch_party(client, message):
    # Usage: /createwatchparty 21459 | 2026-04-10 18:00
    try:
        parts = message.text.split(" ", 1)[1].split(" | ")
        anime_id = int(parts[0])
        start_time = datetime.strptime(parts[1], "%Y-%m-%d %H:%M")
    except Exception:
        return await message.reply("❌ **Usage:** `/createwatchparty <AniList_ID> | YYYY-MM-DD HH:MM`")

    # Fetch from AniList GraphQL
    query = '''
    query ($id: Int) {
      Media (id: $id, type: ANIME) {
        title { romaji english }
        coverImage { extraLarge }
        episodes
      }
    }
    '''
    async with aiohttp.ClientSession() as session:
        async with session.post('https://graphql.anilist.co', json={'query': query, 'variables': {'id': anime_id}}) as resp:
            data = await resp.json()
            media = data['data']['Media']
            title = media['title']['english'] or media['title']['romaji']
            image_url = media['coverImage']['extraLarge']

    event_id = await create_master_event(
        chat_id=message.chat.id, title=f"🎬 Watch Party: {title}",
        start_time=start_time, capacity=100, cost=0, event_type="watchparty",
        metadata={"image_url": image_url}
    )

    caption = (
        f"🍿 **OFFICIAL WATCH PARTY** 🍿\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🎬 **Anime:** {title}\n"
        f"🕒 **Time:** {start_time.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        f"⚠️ *Spoiler Mode will activate automatically when the event starts!*"
    )
    await message.reply_photo(photo=image_url, caption=caption, reply_markup=build_rsvp_keyboard(event_id, 0, 100, 0))

# --- Tournament Creator ---
@Client.on_message(filters.command("createtournament") & filters.group)
async def create_tournament(client, message):
    # Usage: /createtournament 16 | 500 | Weekend Chess
    parts = message.text.split(" | ")
    capacity = int(parts[0].split(" ")[1])
    cost = int(parts[1])
    title = parts[2]
    start_time = datetime.utcnow() # Tournaments start when full for this example
    
    event_id = await create_master_event(
        chat_id=message.chat.id, title=f"🏆 {title}",
        start_time=start_time, capacity=capacity, cost=cost, event_type="tournament"
    )
    
    text = (
        f"🏆 **NEW TOURNAMENT** 🏆\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🎮 **Game:** {title}\n💎 **Entry Fee:** {cost} Coins\n"
        f"👥 **Bracket Size:** {capacity} Players\n\n"
        f"*(Bracket will generate automatically once full!)*"
    )
    await message.reply(text, reply_markup=build_rsvp_keyboard(event_id, 0, capacity, cost))




@Client.on_callback_query(filters.regex(r"^rsvp_(?P<action>yes|no)_(?P<event_id>[a-zA-Z0-9]+)$"))
async def rsvp_handler(client, query):
    action = query.matches[0].group("action")
    event_id = query.matches[0].group("event_id")
    user_id = query.from_user.id
    
    event = await get_event(event_id)
    user_db = await get_user(user_id)
    
    # 1. Enforce No-Show Ban
    if user_db["strikes"] >= 3:
        return await query.answer("❌ You are blacklisted from RSVPs due to 3 No-Show strikes.", show_alert=True)
        
    attendees = event["attendees"]
    cost = event["cost"]
    str_uid = str(user_id)
    
    if action == "yes":
        if str_uid in attendees:
            return await query.answer("✅ You are already registered!", show_alert=True)
            
        if len(attendees) >= event["capacity"]:
            return await query.answer("⚠️ Event is completely full!", show_alert=True)
            
        # Economy Deduction
        if cost > 0:
            success = await alter_coins(user_id, -cost)
            if not success:
                return await query.answer(f"❌ You need {cost} coins for this VIP ticket.", show_alert=True)
                
        # Register User
        attendees[str_uid] = {"checked_in": False}
        await update_event(event_id, attendees=attendees)
        await query.answer(f"🎉 Ticket secured! (-{cost} Coins)" if cost > 0 else "🎉 RSVP Confirmed!", show_alert=True)
        
        # TOURNAMENT BRACKET GENERATOR (Trigger when full)
        if event["event_type"] == "tournament" and len(attendees) == event["capacity"]:
            players = list(attendees.keys())
            random.shuffle(players)
            bracket = [f"Match {i+1}: <a href='tg://user?id={players[i*2]}'>P1</a> vs <a href='tg://user?id={players[i*2+1]}'>P2</a>" for i in range(len(players)//2)]
            
            await client.send_message(
                event["chat_id"], 
                "⚔️ **TOURNAMENT BRACKET GENERATED!** ⚔️\n\n" + "\n".join(bracket)
            )

    elif action == "no":
        if str_uid not in attendees:
            return await query.answer("You weren't on the list.", show_alert=True)
            
        # Refund Logic (Only refund if cancelled 24h before start)
        now = datetime.utcnow()
        if cost > 0:
            if event["start_time"] - now > timedelta(hours=24):
                await alter_coins(user_id, cost)
                await query.answer(f"❌ Cancelled. {cost} Coins refunded.", show_alert=True)
            else:
                await query.answer("❌ Cancelled. No refund (less than 24h to event).", show_alert=True)
        else:
            await query.answer("❌ Cancelled RSVP.")
            
        del attendees[str_uid]
        await update_event(event_id, attendees=attendees)
        
    # Refresh UI
    await query.message.edit_reply_markup(reply_markup=build_rsvp_keyboard(event_id, len(attendees), event["capacity"], cost))




async def event_lifecycle_loop(app):
    while True:
        try:
            now = datetime.utcnow()
            
            # --- 1. Watch Party Spoiler Mode Activator ---
            pending_watch_parties = await events_col.find({"event_type": "watchparty", "status": "pending", "start_time": {"$lte": now}}).to_list(length=None)
            for wp in pending_watch_parties:
                chat_id = wp["chat_id"]
                await events_col.update_one({"event_id": wp["event_id"]}, {"$set": {"status": "active"}})
                
                # Lock chat for non-attendees (pseudo-code logic, requires handling in a separate message filter)
                await app.send_animation(
                    chat_id, 
                    animation="https://media.giphy.com/media/xT0Gqjbcyd1Eb20Aow/giphy.gif", # 3-2-1 Countdown
                    caption="🚨 **SPOILER MODE ACTIVATED** 🚨\nThe watch party has officially begun. Press play!"
                )

            # --- 2. Attendance Enforcer (Ends 1 hour after start) ---
            ending_events = await events_col.find({"status": "active", "start_time": {"$lte": now - timedelta(hours=1)}}).to_list(length=None)
            for event in ending_events:
                await events_col.update_one({"event_id": event["event_id"]}, {"$set": {"status": "finished"}})
                
                # Check who didn't show up
                no_shows = 0
                for user_id_str, data in event["attendees"].items():
                    if not data["checked_in"]:
                        await add_strike(int(user_id_str))
                        no_shows += 1
                        
                if no_shows > 0:
                    await app.send_message(event["chat_id"], f"📋 **Event Concluded.**\n⚠️ {no_shows} users failed to show up and received a No-Show Strike.")

        except Exception as e:
            print(f"Lifecycle Loop Error: {e}")
            
        await asyncio.sleep(60)
