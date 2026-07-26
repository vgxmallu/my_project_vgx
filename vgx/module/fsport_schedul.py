import asyncio
import aiohttp
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import RPCError
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from vgx import app

THESPORTSDB_KEY = "3"  # Free API key for TheSportsDB


mongo_client = AsyncIOMotorClient(Config.MONGO_URL)
db = mongo_client["sports_schedule_bot"]
settings_col = db["schedule_settings"]

# Dictionary tracking running background tasks per chat_id: { chat_id: asyncio.Task }
active_tasks = {}


# ==================== API & DATABASE HELPERS ====================
async def fetch_today_matches():
    """Fetches today's live/scheduled football matches from TheSportsDB."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    url = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}/eventsday.php?d={today}&s=Soccer"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("events") or []
    except Exception as e:
        print(f"[API ERROR] Failed to fetch schedule: {e}")
    return []


async def get_chat_settings(chat_id: int) -> dict:
    """Retrieves settings for a chat from MongoDB or initializes defaults."""
    doc = await settings_col.find_one({"chat_id": chat_id})
    if not doc:
        doc = {
            "chat_id": chat_id,
            "enabled": False,
            "interval": 3600,        # Default: 1h (3600s)
            "interval_label": "1h",
            "auto_delete": 300,      # Default: 300s
            "delete_label": "300s",
            "pin_enabled": False
        }
        await settings_col.update_one({"chat_id": chat_id}, {"$set": doc}, upsert=True)
    return doc


# ==================== UI KEYBOARD BUILDER ====================
def build_control_keyboard(chat_id: int, settings: dict) -> InlineKeyboardMarkup:
    """Builds the control panel keyboard using ONLY InlineKeyboardButton."""
    is_enabled = settings.get("enabled", False)
    pin_enabled = settings.get("pin_enabled", False)
    cur_int = settings.get("interval_label", "1h")
    cur_del = settings.get("delete_label", "300s")

    status_str = "🟢 MODULE ENABLED" if is_enabled else "🔴 MODULE DISABLED"
    pin_str = "📌 Pin Messages: ✅ ON" if pin_enabled else "📌 Pin Messages: ❌ OFF"

    keyboard = InlineKeyboardMarkup([
        # Row 1: Module Enable / Disable Toggle
        [InlineKeyboardButton(status_str, callback_data=f"cfg_toggle_{chat_id}")],
        
        # Header 1
        [InlineKeyboardButton("⏱ Broadcast Interval Settings ⏱", callback_data="cfg_noop")],
        
        # Row 2 & 3: Interval Options (1m, 5m, 20m, 30m, 1h, 2h)
        [
            InlineKeyboardButton(f"{'✅ ' if cur_int=='1m' else ''}1m", callback_data=f"cfg_int_{chat_id}_60_1m"),
            InlineKeyboardButton(f"{'✅ ' if cur_int=='5m' else ''}5m", callback_data=f"cfg_int_{chat_id}_300_5m"),
            InlineKeyboardButton(f"{'✅ ' if cur_int=='20m' else ''}20m", callback_data=f"cfg_int_{chat_id}_1200_20m"),
        ],
        [
            InlineKeyboardButton(f"{'✅ ' if cur_int=='30m' else ''}30m", callback_data=f"cfg_int_{chat_id}_1800_30m"),
            InlineKeyboardButton(f"{'✅ ' if cur_int=='1h' else ''}1h", callback_data=f"cfg_int_{chat_id}_3600_1h"),
            InlineKeyboardButton(f"{'✅ ' if cur_int=='2h' else ''}2h", callback_data=f"cfg_int_{chat_id}_7200_2h"),
        ],
        
        # Header 2
        [InlineKeyboardButton("🗑 Auto-Delete Timer Settings 🗑", callback_data="cfg_noop")],
        
        # Row 4 & 5: Auto Delete Options (30s, 300s, 400s, 2400s, OFF)
        [
            InlineKeyboardButton(f"{'✅ ' if cur_del=='30s' else ''}30s", callback_data=f"cfg_del_{chat_id}_30_30s"),
            InlineKeyboardButton(f"{'✅ ' if cur_del=='300s' else ''}300s", callback_data=f"cfg_del_{chat_id}_300_300s"),
            InlineKeyboardButton(f"{'✅ ' if cur_del=='400s' else ''}400s", callback_data=f"cfg_del_{chat_id}_400_400s"),
        ],
        [
            InlineKeyboardButton(f"{'✅ ' if cur_del=='2400s' else ''}2400s", callback_data=f"cfg_del_{chat_id}_2400_2400s"),
            InlineKeyboardButton(f"{'✅ ' if cur_del=='OFF' else ''}OFF", callback_data=f"cfg_del_{chat_id}_0_OFF"),
        ],
        
        # Row 6: Pin Toggle
        [InlineKeyboardButton(pin_str, callback_data=f"cfg_pin_{chat_id}")],
        
        # Row 7: Close
        [InlineKeyboardButton("❌ Close Control Panel", callback_data="cfg_close")]
    ])
    return keyboard


# ==================== SCHEDULER ENGINE ====================
async def run_broadcast_loop(client: Client, chat_id: int):
    """Background task running match broadcasts for a target chat ID."""
    while True:
        try:
            settings = await get_chat_settings(chat_id)
            if not settings.get("enabled", False):
                break

            interval = settings.get("interval", 3600)
            auto_delete = settings.get("auto_delete", 300)
            pin_enabled = settings.get("pin_enabled", False)

            events = await fetch_today_matches()
            today_str = datetime.utcnow().strftime("%Y-%m-%d")

            text = f"⚽ **LIVE & UPCOMING MATCH SCHEDULE** (`{today_str}`)\n\n"
            if not events:
                text += "❌ *No live or scheduled football matches found for today.*"
            else:
                for event in events[:8]:
                    home = event.get("strHomeTeam", "Home")
                    away = event.get("strAwayTeam", "Away")
                    league = event.get("strLeague", "Football")
                    time_str = event.get("strTime", "TBA")
                    status = event.get("strStatus", "NS")
                    h_score = event.get("intHomeScore")
                    a_score = event.get("intAwayScore")

                    score_str = f"`{h_score} - {a_score}`" if (status != "NS" and h_score is not None) else "VS"

                    text += (
                        f"🏆 **{league}**\n"
                        f"⚔️ **{home}** {score_str} **{away}**\n"
                        f"🕒 Time: `{time_str}` | Status: `{status}`\n\n"
                    )

            # Send Broadcast Message
            msg = await client.send_message(chat_id, text, parse_mode=None)

            # Pin Handler
            if pin_enabled and msg:
                try:
                    await msg.pin(disable_notification=True)
                except RPCError:
                    pass

            # Auto-Delete Handler
            if auto_delete > 0 and msg:
                async def delete_after(target_msg, delay):
                    await asyncio.sleep(delay)
                    try:
                        await target_msg.delete()
                    except RPCError:
                        pass
                asyncio.create_task(delete_after(msg, auto_delete))

            await asyncio.sleep(interval)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[ERROR] Scheduler error in chat {chat_id}: {e}")
            await asyncio.sleep(60)


def sync_scheduler_task(client: Client, chat_id: int, enabled: bool):
    """Starts or stops the background scheduler task for a given chat ID."""
    if chat_id in active_tasks:
        active_tasks[chat_id].cancel()
        del active_tasks[chat_id]
        
    if enabled:
        active_tasks[chat_id] = asyncio.create_task(run_broadcast_loop(client, chat_id))


# ==================== COMMAND HANDLERS ====================
@app.on_message(filters.command("fschedule"))
async def group_schedule_control(client: Client, message: Message):
    """Group Command: Displays the schedule control panel for the current group."""
    chat_id = message.chat.id
    settings = await get_chat_settings(chat_id)
    keyboard = build_control_keyboard(chat_id, settings)
    
    text = (
        f"⚙️ **Live Schedule Broadcast Control**\n"
        f"Target Chat: `{chat_id}`\n\n"
        f"Configure interval, auto-deletion, pinning, and enable/disable states below:"
    )
    await message.reply(text, reply_markup=keyboard, parse_mode=None)


@app.on_message(filters.command("targetschedule"))
async def private_target_schedule_control(client: Client, message: Message):
    """Private Command: Target and control schedule settings for any group ID remotely."""
    if len(message.command) < 2:
        return await message.reply(
            "⚠️ **Usage:** `/targetschedule <group_chat_id>`\n"
            "Example: `/targetschedule -1001234567890`",
            parse_mode=None
        )

    try:
        target_chat_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid Chat ID. Must be a numeric integer.", parse_mode=None)

    settings = await get_chat_settings(target_chat_id)
    keyboard = build_control_keyboard(target_chat_id, settings)
    
    text = (
        f"🎯 **Remote Target Control Panel**\n"
        f"Target Group ID: `{target_chat_id}`\n\n"
        f"You are remotely managing schedule settings for this target chat."
    )
    await message.reply(text, reply_markup=keyboard, parse_mode=None)


# ==================== CALLBACK QUERY HANDLERS ====================
@app.on_callback_query(filters.regex(r"^cfg_toggle_(-?\d+)$"))
async def cb_toggle_module(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group(1))
    settings = await get_chat_settings(chat_id)
    
    new_state = not settings.get("enabled", False)
    await settings_col.update_one({"chat_id": chat_id}, {"$set": {"enabled": new_state}}, upsert=True)
    
    sync_scheduler_task(client, chat_id, new_state)
    await query.answer(f"Module {'ENABLED 🟢' if new_state else 'DISABLED 🔴'}", show_alert=True)
    
    updated_settings = await get_chat_settings(chat_id)
    await query.message.edit_reply_markup(reply_markup=build_control_keyboard(chat_id, updated_settings))


@app.on_callback_query(filters.regex(r"^cfg_int_(-?\d+)_(\d+)_([a-zA-Z0-9]+)$"))
async def cb_set_interval(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group(1))
    seconds = int(query.matches[0].group(2))
    label = query.matches[0].group(3)
    
    await settings_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"interval": seconds, "interval_label": label}},
        upsert=True
    )
    
    settings = await get_chat_settings(chat_id)
    if settings.get("enabled", False):
        sync_scheduler_task(client, chat_id, True)
        
    await query.answer(f"Broadcast interval set to {label}!", show_alert=True)
    await query.message.edit_reply_markup(reply_markup=build_control_keyboard(chat_id, settings))


@app.on_callback_query(filters.regex(r"^cfg_del_(-?\d+)_(\d+)_([a-zA-Z0-9]+)$"))
async def cb_set_autodelete(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group(1))
    seconds = int(query.matches[0].group(2))
    label = query.matches[0].group(3)
    
    await settings_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"auto_delete": seconds, "delete_label": label}},
        upsert=True
    )
    
    settings = await get_chat_settings(chat_id)
    await query.answer(f"Auto-delete timer set to {label}!", show_alert=True)
    await query.message.edit_reply_markup(reply_markup=build_control_keyboard(chat_id, settings))


@app.on_callback_query(filters.regex(r"^cfg_pin_(-?\d+)$"))
async def cb_toggle_pin(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group(1))
    settings = await get_chat_settings(chat_id)
    
    new_pin_state = not settings.get("pin_enabled", False)
    await settings_col.update_one({"chat_id": chat_id}, {"$set": {"pin_enabled": new_pin_state}}, upsert=True)
    
    await query.answer(f"Pin mode {'ENABLED ✅' if new_pin_state else 'DISABLED ❌'}", show_alert=True)
    
    updated_settings = await get_chat_settings(chat_id)
    await query.message.edit_reply_markup(reply_markup=build_control_keyboard(chat_id, updated_settings))


@app.on_callback_query(filters.regex(r"^cfg_close$"))
async def cb_close_panel(client: Client, query: CallbackQuery):
    await query.message.delete()


@app.on_callback_query(filters.regex(r"^cfg_noop$"))
async def cb_noop(client: Client, query: CallbackQuery):
    await query.answer()


# ==================== STARTUP SYNC ====================
async def restore_active_schedulers():
    """Restores broadcast loops for all enabled chats upon bot startup."""
    cursor = settings_col.find({"enabled": True})
    async for doc in cursor:
        chat_id = doc.get("chat_id")
        if chat_id:
            sync_scheduler_task(app, chat_id, True)

