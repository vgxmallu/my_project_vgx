import asyncio
from datetime import datetime, timedelta
from pyrogram import Client
from pyrogram.enums import ParseMode

from vgx.database.footballdb import db, get_group_settings, update_group_setting
from vgx.module.fboll_service import get_live_scores

async def auto_delete_task(client: Client, chat_id: int, message_id: int, delay: int):
    """Schedules automatic message deletion after delay seconds."""
    if delay <= 0:
        return
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id=chat_id, message_ids=message_id)
    except Exception:
        pass

async def send_managed_message(client: Client, chat_id: int, text: str, reply_markup=None):
    """Sends a message while enforcing Auto-Delete and Auto-Pin rules for the chat."""
    settings = await get_group_settings(chat_id)
    
    msg = await client.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Check Auto-Pin Setting
    if settings.get("pin_messages", False):
        try:
            await msg.pin(disable_notification=True)
        except Exception:
            pass

    # Check Auto-Delete Setting
    auto_del = settings.get("auto_delete", 0)
    if auto_del > 0:
        asyncio.create_task(auto_delete_task(client, chat_id, msg.id, auto_del))
        
    return msg

async def live_match_scheduler(client: Client):
    """Background worker for scheduled live football match broadcasts."""
    while True:
        try:
            await asyncio.sleep(30) # Tick every 30 seconds
            now = datetime.utcnow()
            
            # Find groups with active schedule intervals
            cursor = db.group_settings.find({"live_schedule": {"$gt": 0}})
            async for group in cursor:
                chat_id = group["chat_id"]
                interval = group["live_schedule"] # in seconds
                last_run = group.get("last_live_run", datetime.utcnow() - timedelta(days=1))
                
                # Check if module 'live' is enabled for group
                if not group.get("modules", {}).get("live", True):
                    continue

                if (now - last_run).total_seconds() >= interval:
                    live_text = await get_live_scores()
                    await send_managed_message(client, chat_id, f"📡 **AUTOMATED LIVE UPDATES**\n\n{live_text}")
                    await update_group_setting(chat_id, "last_live_run", now)

        except Exception as e:
            print(f"Error in Live Scheduler: {e}")
            await asyncio.sleep(10)
