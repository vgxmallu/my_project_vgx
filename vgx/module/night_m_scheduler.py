import pytz
from datetime import datetime
from pyrogram.types import ChatPermissions
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from vgx.database.night_db import chats, update_settings

async def check_night_mode(app):
    async for chat in chats.find({"enabled": True}):
        chat_id = chat["chat_id"]
        tz = pytz.timezone(chat.get("timezone", "UTC"))
        now = datetime.now(tz).strftime("%H:%M")
        
        start = chat["night_start"]
        end = chat["night_end"]
        
        # Logic for crossing midnight (e.g., 22:00 to 06:00)
        if start < end:
            is_night_time = start <= now < end
        else:
            is_night_time = now >= start or now < end

        # Change state if needed
        if is_night_time and chat.get("current_state") != "night":
            await lock_group(app, chat)
        elif not is_night_time and chat.get("current_state") == "night":
            await unlock_group(app, chat)

async def lock_group(app, chat):
    try:
        await app.set_chat_permissions(chat["chat_id"], ChatPermissions(can_send_messages=False))
        msg = chat.get("night_msg")
        photo = chat.get("night_photo")
        
        if photo:
            await app.send_photo(chat["chat_id"], photo, caption=msg)
        else:
            await app.send_message(chat["chat_id"], msg)
            
        await update_settings(chat["chat_id"], {"current_state": "night"})
    except Exception as e: print(f"Lock Error: {e}")

async def unlock_group(app, chat):
    try:
        await app.set_chat_permissions(chat["chat_id"], ChatPermissions(can_send_messages=True))
        msg = chat.get("morning_msg")
        photo = chat.get("morning_photo")
        
        if photo:
            await app.send_photo(chat["chat_id"], photo, caption=msg)
        else:
            await app.send_message(chat["chat_id"], msg)
            
        await update_settings(chat["chat_id"], {"current_state": "morning"})
    except Exception as e: print(f"Unlock Error: {e}")
