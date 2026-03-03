
import asyncio, random, time
from pyrogram.errors import FloodWait
from vgx.database.quets_db2 import get_due_chats, update_config
from quotes_list import POWERFUL_QUOTES

async def run_quote_scheduler(app):
    while True:
        now = int(time.time())
        due_chats = await get_due_chats(now)
        
        for chat in due_chats:
            chat_id = chat["chat_id"]
            quote = random.choice(POWERFUL_QUOTES)
            
            try:
                msg = await app.send_message(chat_id, quote)
                
                # Update DB to say we sent it, and save the ID for the "Delete Last" button
                await update_config(chat_id, last_sent=now, last_msg_id=msg.id)

                # Execute Auto-Pin
                if chat.get("pin"):
                    await msg.pin(both_sides=True)

                # Execute Auto-Delete
                if chat.get("delete_after", 0) > 0:
                    asyncio.create_task(delayed_delete(msg, chat["delete_after"]))
                    
                await asyncio.sleep(0.5) # Anti-flood delay between groups
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                pass # Bot was likely kicked or blocked
                
        # Check for due chats every 30 seconds to maintain 1m accuracy
        await asyncio.sleep(30) 

async def delayed_delete(msg, delay):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except:
        pass
