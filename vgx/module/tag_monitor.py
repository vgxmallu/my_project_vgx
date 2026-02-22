from pyrogram import Client, filters
from vgx.database.tag_db import get_user_settings
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@Client.on_message(filters.group & ~filters.bot, group=1)
async def monitor_messages(c, m):
    # 1. Check for Mentions or Replies
    is_mention = m.mentioned
    is_reply = m.reply_to_message and m.reply_to_message.from_user.id == c.me.id # (Note: Logic varies for UserBot vs Bot)
    
    # Check for User IDs specifically if you are running this as a bot for multiple users
    # In this example, we assume the bot is protecting the User who started it.
    target_user_id = 12345678 # Replace with your ID or logic to fetch tracked users
    
    settings = await get_user_settings(target_user_id)
    
    if is_mention or (m.reply_to_message and m.reply_to_message.from_user.id == target_user_id):
        alert_text = (
            f"🔔 **New Alert in {m.chat.title}**\n\n"
            f"👤 **From:** {m.from_user.mention}\n"
            f"💬 **Message:** {m.text or '[Media]'}"
        )
        
        # Style buttons based on your preference
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Jump to Message", url=m.link)]
        ])
        
        await c.send_message(
            target_user_id, 
            alert_text, 
            reply_markup=kb,
            disable_notification=settings["muted"]
        )

@Client.on_message(filters.pinned_message & filters.group)
async def monitor_pins(c, m):
    target_user_id = 12345678
    settings = await get_user_settings(target_user_id)
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 View Pin", url=m.link)]
    ])
    
    await c.send_message(
        target_user_id,
        f"📍 **New Pinned Message in {m.chat.title}**",
        reply_markup=kb,
        disable_notification=settings["muted"]
    )
