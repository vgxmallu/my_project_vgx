            

import asyncio
from datetime import datetime
from vgx.database.imdb_db import get_due_posts, set_next_run, queue_deletion, get_due_deletions, remove_deletion
from vgx.module.imdb_fetcher import get_random_imdb_post



async def imdb_background_loop(app):
    while True:
        try:
            now = datetime.utcnow()
            
            # 1. PROCESS NEW POSTS
            due_groups = await get_due_posts(now)
            for group in due_groups:
                chat_id = group["chat_id"]
                
                try:
                    # Fetch a completely random popular movie
                    post_data = await get_random_imdb_post(group["template"])
                    
                    # ✅ Check if our safety engine caught an error (Empty IMDb list)
                    if post_data and post_data.get("error"):
                        print(f"Skipping {chat_id} due to IMDb error: {post_data['error']}")
                        await set_next_run(chat_id, group["interval"])
                        continue # Skip to the next group safely
                    
                    # Send Post
                    if post_data and post_data.get("poster"):
                        msg = await app.send_photo(chat_id, photo=post_data["poster"], caption=post_data["text"])
                    else:
                        msg = await app.send_message(chat_id, text=post_data["text"])
                    
                    # Handle Pin
                    if group["pin"]:
                        await msg.pin(disable_notification=True)
                        
                    # Handle Auto-Delete Queue
                    if group["auto_delete"] > 0:
                        await queue_deletion(chat_id, msg.id, group["auto_delete"])
                        
                except Exception as e:
                    print(f"Failed to post to {chat_id}: {e}")
                    
                # Schedule the next post regardless of success/failure
                await set_next_run(chat_id, group["interval"])

            # 2. PROCESS AUTO-DELETIONS
            due_deletions = await get_due_deletions(now)
            for d in due_deletions:
                try:
                    await app.delete_messages(d["chat_id"], d["message_id"])
                except Exception:
                    pass # Message already deleted or bot lacks admin rights
                
                await remove_deletion(d["_id"])

        except Exception as e:
            print(f"Scheduler Loop Error: {e}")
            
        await asyncio.sleep(15) # Check for tasks every 15 seconds
