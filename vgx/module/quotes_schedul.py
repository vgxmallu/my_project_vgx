
from pyrogram import Client
from pyrogram.errors import MessageNotModified, RPCError
from vgx.database.quets_db2 import get_all_active_chats, update_chat
from quotes_list import POWERFUL_QUOTES


async def delete_later(app: Client, chat_id: int, message_id: int, delay: int):
    """Background task to delete a message after a delay."""
    await asyncio.sleep(delay)
    try:
        await app.delete_messages(chat_id, message_id)
    except RPCError:
        pass

async def run_scheduler(app: Client):
    """Main loop checking for due messages."""
    while True:
        try:
            active_chats = await get_all_active_chats()
            current_time = time.time()

            for chat in active_chats:
                chat_id = chat["chat_id"]
                last_sent = chat.get("last_sent_time", 0)
                interval = chat.get("interval", 3600)

                if (current_time - last_sent) >= interval:
                    quote = random.choice(QUOTES)
                    try:
                        # Send Quote
                        msg = await app.send_message(chat_id, f"✨ {quote}")
                        
                        # Update Database
                        await update_chat(
                            chat_id, 
                            last_msg_id=msg.id, 
                            last_sent_time=time.time()
                        )

                        # Handle Pinning
                        if chat.get("pin"):
                            await msg.pin(disable_notification=True)

                        # Handle Auto-Delete
                        auto_delete_time = chat.get("auto_delete", 0)
                        if auto_delete_time > 0:
                            asyncio.create_task(delete_later(app, chat_id, msg.id, auto_delete_time))

                    except RPCError as e:
                        # If bot was kicked or lacks permissions, optionally disable the chat in DB
                        print(f"Failed to send to {chat_id}: {e}")

        except Exception as e:
            print(f"Scheduler Error: {e}")
            
        await asyncio.sleep(10) # Check every 10 seconds to prevent CPU strain

