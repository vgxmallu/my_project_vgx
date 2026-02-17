import pytz
from datetime import datetime
from pyrogram.types import ChatPermissions
from vgx.database.night_db import chats, update_settings
from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def check_night_mode(app):
    # Find all groups where Night Mode is toggled ON
    async for chat in chats.find({"enabled": True}):
        chat_id = chat["chat_id"]
        tz = pytz.timezone(chat.get("timezone", "UTC"))
        now = datetime.now(tz).strftime("%H:%M")
        
        start = chat["night_start"]
        end = chat["night_end"]
        is_currently_night = chat.get("is_night", False)

        # Logic for crossing midnight (e.g., 22:00 to 07:00)
        if start < end:
            should_be_closed = start <= now < end
        else:
            should_be_closed = now >= start or now < end

        if should_be_closed and not is_currently_night:
            await toggle_group(app, chat, lock=True)
        elif not should_be_closed and is_currently_night:
            await toggle_group(app, chat, lock=False)

async def toggle_group(app, chat, lock):
    chat_id = chat["chat_id"]
    try:
        if lock:
            await app.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=False))
            msg, photo = chat["night_msg"], chat["night_photo"]
        else:
            await app.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=True))
            msg, photo = chat["morning_msg"], chat["morning_photo"]

        if photo:
            await app.send_photo(chat_id, photo, caption=msg)
        else:
            await app.send_message(chat_id, msg)
            
        await update_settings(chat_id, {"is_night": lock})
    except Exception as e:
        print(f"Error in {chat_id}: {e}")

def start_scheduler(app):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_night_mode, "interval", minutes=1, args=[app])
    scheduler.start()
