
import time
from collections import defaultdict, deque
from pyrogram import Client, filters
from pyrogram.types import ChatPermissions
from vgx.database.automod_db import get_warn_settings, add_user_warn, reset_user_warns, increment_stat

# High-speed RAM memory: cache[chat_id][user_id] = deque([(timestamp, msg_id), ...])
flood_cache = defaultdict(lambda: defaultdict(lambda: deque(maxlen=7)))

FLOOD_LIMIT = 5
TIME_WINDOW = 10  # Seconds

@Client.on_message(filters.group & ~filters.bot, group=2)
async def flood_watcher(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    now = time.time()
    
    # 1. Quick enable check
    s = await get_warn_settings(chat_id)
    if not s["enabled"]:
        return

    # Add to RAM cache
    user_history = flood_cache[chat_id][user_id]
    user_history.append((now, message.id))
    
    # 2. Check for Flood (7 msgs in < 10s)
    if len(user_history) == FLOOD_LIMIT:
        time_diff = user_history[-1][0] - user_history[0][0]
        
        if time_diff <= TIME_WINDOW:
            msg_ids_to_delete = [item[1] for item in user_history]
            user_history.clear() # Reset cache
            
            try:
                # Delete the flood messages
                await client.delete_messages(chat_id, msg_ids_to_delete)
                
                # Issue Warning in Database
                current_warns = await add_user_warn(chat_id, user_id)
                max_warns = s["max_warns"]
                
                # Check if punishment is needed
                if current_warns >= max_warns and s["punishment"] != "off":
                    punishment = s["punishment"]
                    action_txt = ""
                    
                    if punishment == "mute":
                        await client.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=False))
                        action_txt = "🔇 **Muted**"
                        await increment_stat(chat_id, deleted=FLOOD_LIMIT, muted=1)
                        
                    elif punishment == "kick":
                        await client.ban_chat_member(chat_id, user_id)
                        await client.unban_chat_member(chat_id, user_id) # Kicks them
                        action_txt = "❗️ **Kicked**"
                        await increment_stat(chat_id, deleted=FLOOD_LIMIT)
                        
                    elif punishment == "ban":
                        await client.ban_chat_member(chat_id, user_id)
                        action_txt = "🚫 **Banned**"
                        await increment_stat(chat_id, deleted=FLOOD_LIMIT, banned=1)
                        
                    # Reset their warns since they were punished
                    await reset_user_warns(chat_id, user_id)
                    
                    await message.reply(
                        f"⚠️ **Action Taken** ⚠️\n"
                        f"{message.from_user.mention} reached {current_warns}/{max_warns} warnings.\n"
                        f"**Punishment applied:** {action_txt}"
                    )
                    
                else:
                    # Just issue a warning
                    await increment_stat(chat_id, warns=1, deleted=FLOOD_LIMIT)
                    await message.reply(
                        f"⚠️ **FLOOD WARNING** ⚠️\n"
                        f"{message.from_user.mention}, please stop spamming!\n"
                        f"**Warns:** {current_warns}/{max_warns}"
                    )
                    
            except Exception as e:
                print(f"Failed to execute mod action in {chat_id}: {e}")
