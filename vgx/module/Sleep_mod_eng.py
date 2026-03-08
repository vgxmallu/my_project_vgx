import re
import time
from collections import defaultdict, deque
from pyrogram import Client, filters
from pyrogram.enums import MessageEntityType, ChatMemberStatus
from pyrogram.types import ChatPermissions
from vgx.database.sleepmod_db import get_nw_settings

# High-speed RAM cache strictly for Night Mode flood detection (3 msgs / 5 secs)
night_flood_cache = defaultdict(lambda: defaultdict(lambda: deque(maxlen=3)))

# Basic regex for crypto spam detection during the day
CRYPTO_REGEX = re.compile(r"(?i)(crypto|bitcoin|eth|airdrop|wallet)\.(com|io|net)|t\.me\/[a-zA-Z0-9_]+")

async def is_admin(client, chat_id: int, user_id: int) -> bool:
    """Helper to ensure we don't punish admins."""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except Exception:
        return False

def has_link(message):
    """Checks if a message contains any URL or text link."""
    if not message.entities:
        return False
    for ent in message.entities:
        if ent.type in [MessageEntityType.URL, MessageEntityType.TEXT_LINK]:
            return True
    return False

@Client.on_message(filters.group & ~filters.bot, group=3)
async def adaptive_security_watcher(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # 1. Check if module is enabled
    s = await get_nw_settings(chat_id)
    if not s["enabled"]:
        return

    mode = s["current_mode"]

    # ==========================================
    # 🛡 STRICT MODE (NIGHT)
    # ==========================================
    if mode == "strict":
        # A. Check for illegal content (Links, Media, Forwards)
        if message.media or message.forward_date or has_link(message):
            if not await is_admin(client, chat_id, user_id):
                await message.delete()
                return # Stop processing, it's already deleted
        
        # B. Nightwatch Flood Detection (3 msgs in 5 seconds)
        now = time.time()
        user_history = night_flood_cache[chat_id][user_id]
        user_history.append((now, message.id))
        
        if len(user_history) == 3:
            time_diff = user_history[-1][0] - user_history[0][0]
            if time_diff <= 5: # 5 seconds
                if not await is_admin(client, chat_id, user_id):
                    # Delete the flood
                    msg_ids = [item[1] for item in user_history]
                    user_history.clear()
                    
                    try:
                        await client.delete_messages(chat_id, msg_ids)
                        # Mute them indefinitely until an admin checks
                        await client.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=False))
                        await message.reply(f"🛡 **NIGHTWATCH:** {message.from_user.mention} has been auto-muted for night-time spamming.")
                    except Exception:
                        pass
                else:
                    user_history.clear() # Clear it for admins so it doesn't build up

    # ==========================================
    # ☀️ LENIENT MODE (DAY)
    # ==========================================
    elif mode == "lenient":
        # Only block specific malicious links (Crypto/Airdrops), allow everything else
        if message.text or message.caption:
            text_to_check = str(message.text or message.caption)
            if CRYPTO_REGEX.search(text_to_check):
                if not await is_admin(client, chat_id, user_id):
                    await message.delete()
                    # Optional: await message.reply("⚠️ Crypto/Promo links are not allowed here.")
