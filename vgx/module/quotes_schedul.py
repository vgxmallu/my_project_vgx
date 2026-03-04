import asyncio
import random
import time
from pyrogram.errors import FloodWait
from vgx.database.quets_db2 import get_due_chats, update_chat
from quotes_list import POWERFUL_QUOTES

async def auto_delete_task(app, chat_id: int, msg_id: int, delay: int):
    """Waits securely in the background, then deletes the specific message."""
    await asyncio.sleep(delay)
    try:
        await app.delete_messages(chat_id, msg_id)
    except Exception:
        pass # Message might already be deleted or bot lost admin rights

async def quote_worker(app):
    """The central loop handling the timed logic."""
    while True:
        try:
            due_chats = await get_due_chats()
            now = int(time.time())
            
            for chat in due_chats:
                chat_id = chat["chat_id"]
                quote = random.choice(QUOTES)
                
                try:
                    # 1. Dispatch the Quote
                    msg = await app.send_message(chat_id, quote)
                    
                    # 2. Log metadata to DB
                    await update_chat(chat_id, last_sent=now, last_msg_id=msg.id)

                    # 3. Handle Auto-Pinning
                    if chat.get("pin"):
                        await msg.pin(both_sides=True)

                    # 4. Handle Auto-Deletion Task Spawning
                    del_time = chat.get("delete_after", 0)
                    if del_time > 0:
                        asyncio.create_task(auto_delete_task(app, chat_id, msg.id, del_time))
                        
                except FloodWait as e:
                    await asyncio.sleep(e.value) # Essential for bot survival 
                except Exception as e:
                    print(f"Skipping group {chat_id}: {e}")
                    
            # Poll every 20 seconds to guarantee exact 1-minute interval triggers
            await asyncio.sleep(20) 
            
        except Exception as e:
            print(f"Scheduler Engine Error: {e}")
            await asyncio.sleep(10)
            
