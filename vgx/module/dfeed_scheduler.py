import time
from pyrogram.types import InputMediaPhoto, InputMediaVideo
from vgx.database.dfeed_db import db, get_chat_settings, get_next_item, update_settings, queue
from apscheduler.schedulers.asyncio import AsyncIOScheduler



async def drip_engine(app):
    # Find all active chats
    async for chat in db.settings.find({"is_active": True}):
        chat_id = chat["chat_id"]
        now = time.time()
        
        # Check if interval has passed
        if now - chat.get("last_drip_time", 0) >= chat.get("interval", 3600):
            item = await get_next_item(chat_id)
            if not item:
                continue # No content left in queue
            
            # --- Advanced Twist: Delete Last Message ---
            if chat.get("last_msg_id"):
                try:
                    await app.delete_messages(chat_id, chat["last_msg_id"])
                except:
                    pass # Message might have been manually deleted
            
            # --- Send New Content ---
            sent_msg = None
            f_id, f_type, cap = item["file_id"], item["file_type"], item["caption"]
            
            try:
                if f_type == "photo":
                    sent_msg = await app.send_photo(chat_id, f_id, caption=cap)
                elif f_type == "video":
                    sent_msg = await app.send_video(chat_id, f_id, caption=cap)
                elif f_type == "document":
                    sent_msg = await app.send_document(chat_id, f_id, caption=cap)
                
                # Update DB with last post info
                await update_settings(chat_id, {
                    "last_drip_time": now,
                    "last_msg_id": sent_msg.id if sent_msg else None
                })
            except Exception as e:
                print(f"Drip Error in {chat_id}: {e}")

def start_df_scheduler(app):
    scheduler = AsyncIOScheduler()
    # Check every minute
    scheduler.add_job(drip_engine, "interval", minutes=1, args=[app])
    scheduler.start()
