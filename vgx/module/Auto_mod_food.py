

import time
from datetime import datetime, timedelta
from collections import defaultdict, deque
from pyrogram import Client, filters
from pyrogram.types import ChatPermissions
from vgx.database.automod_db import get_mod_settings, increment_stat

# High-speed RAM memory to track timestamps and message IDs
# Structure: cache[chat_id][user_id] = deque([(timestamp, msg_id), ...])
flood_cache = defaultdict(lambda: defaultdict(lambda: deque(maxlen=7)))

FLOOD_LIMIT = 7
TIME_WINDOW = 10  # Seconds
MUTE_DURATION_HOURS = 1  # How long the user stays muted

@Client.on_message(filters.group & ~filters.bot, group=2)
async def flood_watcher(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    now = time.time()
    
    # 1. Quick check if module is enabled
    s = await get_mod_settings(chat_id)
    if not s["enabled"]:
        return

    # Add current message to the user's high-speed RAM cache
    user_history = flood_cache[chat_id][user_id]
    user_history.append((now, message.id))
    
    # 2. Check if they have reached exactly 7 messages
    if len(user_history) == FLOOD_LIMIT:
        # Calculate time difference between their 1st message and 7th message
        time_diff = user_history[-1][0] - user_history[0][0]
        
        if time_diff <= TIME_WINDOW:
            # 🛑 FLOOD DETECTED! 🛑
            msg_ids_to_delete = [item[1] for item in user_history]
            
            # Clear their cache so they don't trigger it again while being muted
            user_history.clear()
            
            try:
                # 3. Delete all 7 spam messages at once
                await client.delete_messages(chat_id, msg_ids_to_delete)
                
                # 4. MUTE THE USER
                # Calculate the exact time they should be unmuted
                unmute_time = datetime.now() + timedelta(hours=MUTE_DURATION_HOURS)
                
                await client.restrict_chat_member(
                    chat_id,
                    user_id,
                    ChatPermissions(can_send_messages=False),
                    until_date=unmute_time
                )
                
                # 5. Issue the Warning & Announcement
                await message.reply(
                    f"⚠️ **FLOOD DETECTED** ⚠️\n"
                    f"{message.from_user.mention}, you sent {FLOOD_LIMIT} messages in under {TIME_WINDOW} seconds.\n"
                    f"🔇 **Action:** Muted for {MUTE_DURATION_HOURS} hour(s) to cool down."
                )
                
                # 6. Update Weekly Stats in MongoDB! (Adding +1 to users_muted)
                await increment_stat(chat_id, warns=1, deleted=FLOOD_LIMIT, muted=1)
                
            except Exception as e:
                # Failsafe: Usually triggers if the bot doesn't have "Ban Users" or "Delete Messages" admin rights
                print(f"Failed to execute flood mute in {chat_id}: {e}")
