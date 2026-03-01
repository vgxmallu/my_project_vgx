import asyncio, random, time
from pyrogram.errors import FloodWait
from vgx.database.quets_db2 import get_all_active_chats, update_chat
from quotes_list import POWERFUL_QUOTES

async def run_quote_scheduler(app):
    while True:
        now = int(time.time())
        active_chats = await get_all_active_chats()
        
        async for chat in active_chats:
            # Check if interval has passed
            if now - chat.get("last_sent", 0) >= (chat["interval"] * 60):
                quote = random.choice(POWERFUL_QUOTES)
                try:
                    msg = await app.send_message(chat["chat_id"], quote)
                    
                    # Update database with last message ID
                    await update_chat(chat["chat_id"], last_sent=now, last_msg_id=msg.id)

                    if chat.get("pin"):
                        await msg.pin(both_sides=True)

                    if chat.get("delete_after", 0) > 0:
                        asyncio.create_task(auto_delete_waiter(msg, chat["delete_after"]))

                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception:
                    pass # Ignore if kicked from group
        
        await asyncio.sleep(30) # Check every 30 seconds

async def auto_delete_waiter(msg, delay):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except:
        pass
