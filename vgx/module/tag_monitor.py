from pyrogram import Client, filters
from pyrogram.enums import MessageEntityType
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import PeerIdInvalid, UserIsBlocked
from vgx.database.tag_db import get_user_settings, get_user_by_username
import time

# Dictionary to handle the "Smart" cooldown mode (prevents spamming alerts)
last_alert_time = {}

async def send_alert(client, target_user_id, alert_text, url):
    settings = await get_user_settings(target_user_id)
    if not settings:
        return # User hasn't started the bot, we can't PM them.

    # "Smart" Mode Logic: Only notify if they haven't been alerted in the last 5 minutes
    if settings.get("mode") == "smart":
        last_time = last_alert_time.get(target_user_id, 0)
        if time.time() - last_time < 300: # 300 seconds = 5 minutes
            return
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Jump to Message", url=url)]])
    
    try:
        await client.send_message(
            target_user_id, 
            alert_text, 
            reply_markup=kb, 
            disable_notification=settings.get("muted", False)
        )
        last_alert_time[target_user_id] = time.time()
    except (PeerIdInvalid, UserIsBlocked):
        pass # User blocked the bot or deleted chat

# Listen to BOTH new messages AND edited messages!
@Client.on_message(filters.group & ~filters.bot, group=1)
@Client.on_edited_message(filters.group & ~filters.bot, group=1)
async def process_mentions_and_replies(c, m):
    notified_users = set()
    
    # 1. CHECK REPLIES
    if m.reply_to_message and m.reply_to_message.from_user:
        target_id = m.reply_to_message.from_user.id
        if target_id != m.from_user.id and target_id not in notified_users:
            text = f"🔶 **New Reply in {m.chat.title}**\n👤 {m.from_user.mention} replied to you!"
            await send_alert(c, target_id, text, m.link)
            notified_users.add(target_id)

    # 2. CHECK TAGS (Mentions)
    if m.entities or m.caption_entities:
        entities = m.entities or m.caption_entities
        text_content = m.text or m.caption
        
        for entity in entities:
            target_id = None
            
            # Inline Text Mention (e.g. clicking a name to tag them)
            if entity.type == MessageEntityType.TEXT_MENTION:
                target_id = entity.user.id
                
            # @username Mention
            elif entity.type == MessageEntityType.MENTION:
                username = text_content[entity.offset:entity.offset + entity.length].strip("@")
                db_user = await get_user_by_username(username)
                if db_user:
                    target_id = db_user["user_id"]
            
            if target_id and target_id != m.from_user.id and target_id not in notified_users:
                alert_text = f"🔶 **You were mentioned in {m.chat.title}**\n👤 By {m.from_user.mention}"
                await send_alert(c, target_id, alert_text, m.link)
                notified_users.add(target_id)

@Client.on_message(filters.pinned_message & filters.group)
async def process_pins(c, m):
    # Note: To notify everyone in the DB about a pin, we'd have to loop through all users
    # For a large bot, this is heavy. We'll skip the loop here for safety, but this is the trigger point.
    pass 
