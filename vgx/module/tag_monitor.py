from pyrogram import Client, filters
from vgx.database.tag_db import get_user_config
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@Client.on_message(filters.group & ~filters.bot, group=1)
async def notification_handler(c, m):
    # This bot acts for the user who started it (tracked_user_id)
    # For a multi-user bot, you would iterate through mentioned IDs
    
    # 1. Detection Logic
    is_tag = m.mentioned 
    is_reply = m.reply_to_message and m.reply_to_message.from_user.id == 12345678 # Replace with real ID
    
    if is_tag or is_reply:
        user_id = 12345678 
        settings = await get_user_config(user_id)
        
        # 'Smart' check would ideally check 'last_seen', 
        # but here we simulate the logic based on the user's toggle
        
        alert_text = (
            f"🔶 **New Alert in {m.chat.title}**\n"
            f"👤 **From:** {m.from_user.mention}\n"
            f"💬 **Message:** {m.text or '[Media]'}"
        )
        
        # Handy button to jump to the correct place
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Jump to Message", url=m.link)]
        ])
        
        await c.send_message(
            user_id, 
            alert_text, 
            reply_markup=kb,
            disable_notification=settings["muted"] # Handle muted style
        )

@Client.on_message(filters.pinned_message & filters.group)
async def pin_handler(c, m):
    # Notify for pinned messages
    user_id = 12345678
    settings = await get_user_config(user_id)
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📌 View Pin", url=m.link)]])
    await c.send_message(
        user_id, 
        f"📍 **New Pinned Message in {m.chat.title}**",
        reply_markup=kb,
        disable_notification=settings["muted"]
    )
