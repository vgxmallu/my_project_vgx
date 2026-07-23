import asyncio
from datetime import datetime, timedelta
from pyrogram import Client
from vgx.database.footballdb import db, get_group_settings, update_group_setting
from vgx.module.football_api import get_live_scores

async def auto_delete_task(client: Client, chat_id: int, message_id: int, delay: int):
    if delay <= 0: return
    await asyncio.sleep(delay)
    try: await client.delete_messages(chat_id, message_id)
    except Exception: pass

async def send_managed_message(client: Client, chat_id: int, text: str, reply_markup=None):
    settings = await get_group_settings(chat_id)
    msg = await client.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
    
    if settings.get("pin_messages", False):
        try: await msg.pin(disable_notification=True)
        except Exception: pass

    auto_del = settings.get("auto_delete", 0)
    if auto_del > 0: 
        asyncio.create_task(auto_delete_task(client, chat_id, msg.id, auto_del))
    return msg

async def match_scheduler(client: Client):
    while True:
        try:
            await asyncio.sleep(30) # Tick every 30 seconds
            now = datetime.utcnow()
            async for group in db.group_settings.find({"live_schedule": {"$gt": 0}}):
                chat_id = group["chat_id"]
                
                # Check if module is disabled
                if not group.get("modules", {}).get("live", True): continue

                schedule_time = group["live_schedule"]
                last_run = group.get("last_live_run", now - timedelta(days=1))

                if (now - last_run).total_seconds() >= schedule_time:
                    live_text = await get_live_scores()
                    await send_managed_message(client, chat_id, f"📡 **SCHEDULED LIVE UPDATE**\n\n{live_text}")
                    await update_group_setting(chat_id, "last_live_run", now)
        except Exception as e:
            print(f"Scheduler Error: {e}")
