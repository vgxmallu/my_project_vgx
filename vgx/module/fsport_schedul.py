import asyncio
import aiohttp
import pyrogram
from datetime import datetime, timezone
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
from vgx import app
from config import Config


THESPORTSDB_KEY = "3"

# ==================== INITIALIZATION ====================
db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["sports_schedule_bot"]
settings_col = db["schedule_settings"]
votes_col = db["match_votes"]

# ==================== API HELPERS ====================
async def fetch_api(endpoint: str, params: dict = {}):
    url = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}/{endpoint}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        print(f"API Error: {e}")
    return {}

async def get_team_last_points(team_id: str) -> str:
    """Fetches the previous match score/points for a team to show performance."""
    data = await fetch_api("eventslast.php", {"id": team_id})
    events = data.get("results")
    if not events:
        return "N/A"
    
    last = events[0]
    h_score = last.get('intHomeScore', '0')
    a_score = last.get('intAwayScore', '0')
    return f"{last['strHomeTeam']} {h_score}-{a_score} {last['strAwayTeam']}"

async def fetch_live_matches():
    """Fetches today's matches and grabs past performance for the first match."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data = await fetch_api("eventsday.php", {"d": today, "s": "Soccer"})
    events = data.get("events", [])
    
    matches = []
    for e in events[:3]:  # Limit to 3 to prevent API spam and huge messages
        home_id = e.get("idHomeTeam")
        away_id = e.get("idAwayTeam")
        home_form = await get_team_last_points(home_id) if home_id else "N/A"
        away_form = await get_team_last_points(away_id) if away_id else "N/A"
        
        matches.append({
            "id": e.get("idEvent"),
            "league": e.get("strLeague", "Tournament"),
            "home": e.get("strHomeTeam", "Home"),
            "away": e.get("strAwayTeam", "Away"),
            "time": f"{e.get('dateEvent')} at {e.get('strTime')} (UTC)",
            "home_form": home_form,
            "away_form": away_form
        })
    return matches

# ==================== DATABASE HELPERS ====================
async def get_chat_config(chat_id: int) -> dict:
    doc = await settings_col.find_one({"chat_id": chat_id})
    if not doc:
        doc = {
            "chat_id": chat_id,
            "enabled": False,
            "interval": 3600,
            "interval_label": "1h",
            "auto_delete": 0,
            "delete_label": "OFF",
            "pin": False,
            "last_sent": 0
        }
        await settings_col.update_one({"chat_id": chat_id}, {"$set": doc}, upsert=True)
    return doc

# ==================== UI KEYBOARD BUILDER ====================
def control_panel_ui(chat_id: int, conf: dict) -> InlineKeyboardMarkup:
    en_str = "🟢 MODULE ON" if conf.get("enabled") else "🔴 MODULE OFF"
    pin_str = "📌 PIN: ON" if conf.get("pin") else "📌 PIN: OFF"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(en_str, callback_data=f"set_tog_{chat_id}"),
         InlineKeyboardButton("🚫 DISABLE TARGET", callback_data=f"set_dis_{chat_id}")],
        
        [InlineKeyboardButton("--- Broadcast Intervals ---", callback_data="noop")],
        [InlineKeyboardButton(f"{'✅ ' if conf['interval']==60 else ''}1m", callback_data=f"set_int_{chat_id}_60_1m"),
         InlineKeyboardButton(f"{'✅ ' if conf['interval']==300 else ''}5m", callback_data=f"set_int_{chat_id}_300_5m"),
         InlineKeyboardButton(f"{'✅ ' if conf['interval']==1200 else ''}20m", callback_data=f"set_int_{chat_id}_1200_20m")],
        [InlineKeyboardButton(f"{'✅ ' if conf['interval']==1800 else ''}30m", callback_data=f"set_int_{chat_id}_1800_30m"),
         InlineKeyboardButton(f"{'✅ ' if conf['interval']==3600 else ''}1h", callback_data=f"set_int_{chat_id}_3600_1h")],
        
        [InlineKeyboardButton("--- Auto Delete Timers ---", callback_data="noop")],
        [InlineKeyboardButton(f"{'✅ ' if conf['auto_delete']==30 else ''}30s", callback_data=f"set_del_{chat_id}_30_30s"),
         InlineKeyboardButton(f"{'✅ ' if conf['auto_delete']==300 else ''}300s", callback_data=f"set_del_{chat_id}_300_300s")],
        [InlineKeyboardButton(f"{'✅ ' if conf['auto_delete']==400 else ''}400s", callback_data=f"set_del_{chat_id}_400_400s"),
         InlineKeyboardButton(f"{'✅ ' if conf['auto_delete']==2400 else ''}2400s", callback_data=f"set_del_{chat_id}_2400_2400s")],
        [InlineKeyboardButton(f"{'✅ ' if conf['auto_delete']==0 else ''}OFF", callback_data=f"set_del_{chat_id}_0_OFF")],
        
        [InlineKeyboardButton(pin_str, callback_data=f"set_pin_{chat_id}")],
        [InlineKeyboardButton("❌ Close", callback_data="close_ui")]
    ])

def build_voting_keyboard(match_id: str, h_name: str, a_name: str, votes: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{h_name} ({votes.get('h', 0)})", callback_data=f"vote_{match_id}_h"),
         InlineKeyboardButton(f"Draw ({votes.get('d', 0)})", callback_data=f"vote_{match_id}_d"),
         InlineKeyboardButton(f"{a_name} ({votes.get('a', 0)})", callback_data=f"vote_{match_id}_a")]
    ])

# ==================== COMMAND HANDLERS ====================
@app.on_message(filters.command("schedules"))
async def grosbup_schedule(client: Client, message: Message):
    conf = await get_chat_config(message.chat.id)
    await message.reply(f"⚙️ **Live Match Setup (Chat: {message.chat.id})**", reply_markup=control_panel_ui(message.chat.id, conf))

@app.on_message(filters.command("targetschedule") & filters.private)
async def tarhget_schedule(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("⚠️ Use: `/targetschedule <group_id>`")
    try:
        tgt = int(message.command[1])
        conf = await get_chat_config(tgt)
        await message.reply(f"🎯 **Targeting: {tgt}**", reply_markup=control_panel_ui(tgt, conf))
    except ValueError:
        await message.reply("❌ Invalid Chat ID.")

# ==================== CALLBACK HANDLERS ====================
@app.on_callback_query(filters.regex(r"^set_tog_(-?\d+)$"))
async def cb_toggle(c: Client, q: CallbackQuery):
    cid = int(q.matches[0].group(1))
    conf = await get_chat_config(cid)
    new_st = not conf.get("enabled")
    await settings_col.update_one({"chat_id": cid}, {"$set": {"enabled": new_st}})
    await q.message.edit_reply_markup(control_panel_ui(cid, await get_chat_config(cid)))

@app.on_callback_query(filters.regex(r"^set_dis_(-?\d+)$"))
async def cb_disable(c: Client, q: CallbackQuery):
    cid = int(q.matches[0].group(1))
    await settings_col.update_one({"chat_id": cid}, {"$set": {"enabled": False}})
    await q.answer("❌ Target chat module completely disabled.", show_alert=True)
    await q.message.edit_reply_markup(control_panel_ui(cid, await get_chat_config(cid)))

@app.on_callback_query(filters.regex(r"^set_int_(-?\d+)_(\d+)_([\w]+)$"))
async def cb_interval(c: Client, q: CallbackQuery):
    cid = int(q.matches[0].group(1))
    sec = int(q.matches[0].group(2))
    lbl = q.matches[0].group(3)
    await settings_col.update_one({"chat_id": cid}, {"$set": {"interval": sec, "interval_label": lbl}})
    await q.message.edit_reply_markup(control_panel_ui(cid, await get_chat_config(cid)))

@app.on_callback_query(filters.regex(r"^set_del_(-?\d+)_(\d+)_([\w]+)$"))
async def cb_delete(c: Client, q: CallbackQuery):
    cid = int(q.matches[0].group(1))
    sec = int(q.matches[0].group(2))
    lbl = q.matches[0].group(3)
    await settings_col.update_one({"chat_id": cid}, {"$set": {"auto_delete": sec, "delete_label": lbl}})
    await q.message.edit_reply_markup(control_panel_ui(cid, await get_chat_config(cid)))

@app.on_callback_query(filters.regex(r"^set_pin_(-?\d+)$"))
async def cb_pin(c: Client, q: CallbackQuery):
    cid = int(q.matches[0].group(1))
    conf = await get_chat_config(cid)
    await settings_col.update_one({"chat_id": cid}, {"$set": {"pin": not conf.get("pin")}})
    await q.message.edit_reply_markup(control_panel_ui(cid, await get_chat_config(cid)))

@app.on_callback_query(filters.regex(r"^close_ui$"))
async def cb_close(c: Client, q: CallbackQuery):
    await q.message.delete()

@app.on_callback_query(filters.regex(r"^vote_(\w+)_([hda])$"))
async def cb_vote(c: Client, q: CallbackQuery):
    m_id = q.matches[0].group(1)
    choice = q.matches[0].group(2)
    user_id = q.from_user.id
    
    # Check if user already voted on this specific match broadcast
    vote_data = await votes_col.find_one({"msg_id": q.message.id})
    if vote_data and user_id in vote_data.get("users", []):
        return await q.answer("You already voted!", show_alert=True)
    
    # Update vote count
    await votes_col.update_one(
        {"msg_id": q.message.id},
        {"$inc": {choice: 1}, "$push": {"users": user_id}, "$set": {"match_id": m_id}},
        upsert=True
    )
    new_vote = await votes_col.find_one({"msg_id": q.message.id})
    
    # We must extract names from the existing keyboard to rebuild it properly
    kb = q.message.reply_markup.inline_keyboard[0]
    h_name = kb[0].text.split(" (")[0]
    a_name = kb[2].text.split(" (")[0]
    
    await q.message.edit_reply_markup(build_voting_keyboard(m_id, h_name, a_name, new_vote))
    await q.answer("Vote recorded!")

@app.on_callback_query(filters.regex(r"^noop$"))
async def cb_noop(c: Client, q: CallbackQuery):
    await q.answer()

# ==================== MAIN SCHEDULER LOOP ====================
async def sportsdb_scheduler_loop(app: Client):
    """Event-driven scheduled message logic."""
    while True:
        try:
            now = datetime.now(timezone.utc).timestamp()
            cursor = settings_col.find({"enabled": True})
            
            async for conf in cursor:
                chat_id = conf["chat_id"]
                last_sent = conf.get("last_sent", 0)
                interval = conf.get("interval", 3600)
                
                # Check if it's time to send based on customized interval
                if now - last_sent >= interval:
                    matches = await fetch_live_matches()
                    if not matches:
                        continue
                        
                    for m in matches:
                        text = (
                            f"⚽ **LIVE MATCH SCHEDULE** ⚽\n\n"
                            f"🏆 **League:** {m['league']}\n"
                            f"⚔️ **{m['home']}** vs **{m['away']}**\n"
                            f"⏰ **Exact Start Time:** `{m['time']}`\n\n"
                            f"📊 **PREVIOUS TEAM PERFORMANCE:**\n"
                            f"🔹 *{m['home']} Last:* {m['home_form']}\n"
                            f"🔹 *{m['away']} Last:* {m['away_form']}\n\n"
                            f"👇 **VOTE WHO WILL WIN BELOW!** 👇"
                        )
                        
                        kb = build_voting_keyboard(m['id'], m['home'], m['away'], {})
                        msg = await app.send_message(chat_id, text, reply_markup=kb)
                        
                        # Initialize voting DB document
                        await votes_col.insert_one({
                            "msg_id": msg.id, "match_id": m['id'], 
                            "h": 0, "d": 0, "a": 0, "users": []
                        })
                        
                        if conf.get("pin"):
                            try:
                                await msg.pin(disable_notification=True)
                            except: pass
                            
                        # Handle auto-delete
                        if conf.get("auto_delete", 0) > 0:
                            async def delete_task(target_msg, delay):
                                await asyncio.sleep(delay)
                                try:
                                    await target_msg.delete()
                                    await votes_col.delete_one({"msg_id": target_msg.id})
                                except: pass
                            asyncio.create_task(delete_task(msg, conf["auto_delete"]))
                    
                    # Update last_sent timestamp
                    await settings_col.update_one({"chat_id": chat_id}, {"$set": {"last_sent": now}})
                    
        except Exception as e:
            print(f"Loop Error: {e}")
            
        await asyncio.sleep(20)  # Short sleep to check timers frequently
