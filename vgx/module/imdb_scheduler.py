import asyncio
from datetime import datetime, timedelta
from vgx.database.imdb_db import imdb_queue, imdb_deletions, get_settings, add_to_deletion
from vgx.module.imdb_fetcher import get_imdb_post

async def imdb_worker(app):
    while True:
        try:
            now = datetime.utcnow()
            
            # --- 1. Process Movie Posts ---
            async for task in imdb_queue.find({"next_run": {"$lte": now}}):
                chat_id = task["chat_id"]
                s = await get_settings(chat_id)
                
                if s["enabled"]:
                    # Fetch IMDb Data
                    post_data = await get_imdb_post(task["query"], s["template"])
                    
                    if not post_data["error"]:
                        try:
                            # Send Post
                            if post_data["poster"]:
                                msg = await app.send_photo(chat_id, photo=post_data["poster"], caption=post_data["text"])
                            else:
                                msg = await app.send_message(chat_id, text=post_data["text"])
                                
                            # Handle Pinning
                            if s["pin_message"]:
                                await msg.pin()
                                
                            # Handle Auto-Delete
                            if s["auto_delete"] > 0:
                                del_time = now + timedelta(seconds=s["auto_delete"])
                                await add_to_deletion(chat_id, msg.id, del_time)
                                
                        except Exception as e:
                            print(f"Failed to post to {chat_id}: {e}")
                
                # Reschedule or remove task
                # (For this example, we delete it from queue after posting once. 
                # If you want it to loop the same movie, you'd update next_run here)
                await imdb_queue.delete_one({"_id": task["_id"]})
                
            # --- 2. Process Auto-Deletions ---
            async for del_task in imdb_deletions.find({"delete_at": {"$lte": now}}):
                try:
                    await app.delete_messages(del_task["chat_id"], del_task["message_id"])
                except:
                    pass
                await imdb_deletions.delete_one({"_id": del_task["_id"]})

        except Exception as e:
            print(f"IMDb Scheduler Error: {e}")
            
        await asyncio.sleep(15) # Check queues every 15 seconds
