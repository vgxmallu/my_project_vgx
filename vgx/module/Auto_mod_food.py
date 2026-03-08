import time
from collections import defaultdict, deque
from pyrogram import Client, filters
from vgx.database.automod_db import get_mod_settings, increment_stat

# High-speed RAM memory to track timestamps and message IDs
# Structure: cache[chat_id][user_id] = deque([(timestamp, msg_id), ...])
flood_cache = defaultdict(lambda: defaultdict(lambda: deque(maxlen=7)))

FLOOD_LIMIT = 5
TIME_WINDOW = 10  # Seconds

@Client.on_message(filters.group & ~filters.bot, group=2)
async def flood_watcher(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    msg_id = message.id
    now = time.time()
    
    # 1. Quick check if module is enabled
    s = await get_mod_settings(chat_id)
    if not s["enabled"]:
        return

    user_history = flood_cache[chat_id][user_id]
    user_history.append((now, msg_id))
    
    # 2. Check if they have reached 7 messages
    if len(user_history) == FLOOD_LIMIT:
        # Calculate time difference between the 1st message and the 7th message
        time_diff = user_history[-1][0] - user_history[0][0]
        
        if time_diff <= TIME_WINDOW:
            # 🛑 FLOOD DETECTED! 🛑
            msg_ids_to_delete = [item[1] for item in user_history]
            
            # Clear their cache so they don't instantly trigger it again
            user_history.clear()
            
            try:
                # Delete all 7 messages at once
                await client.delete_messages(chat_id, msg_ids_to_delete)
                
                # Issue Warning
                warn_msg = await message.reply(
                    f"⚠️ **FLOOD WARNING** ⚠️\n"
                    f"{message.from_user.mention}, you sent {FLOOD_LIMIT} messages in under {TIME_WINDOW} seconds.\n"
                    f"Please slow down or you will be muted."
                )
                
                # Update Weekly Stats in MongoDB!
                await increment_stat(chat_id, warns=1, deleted=FLOOD_LIMIT)
                
            except Exception as e:
                print(f"Failed to execute flood action in {chat_id}: {e}")
