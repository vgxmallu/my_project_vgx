from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.quets_db import enable_quotes, disable_quotes, is_enabled

@Client.on_message(filters.command("quotes"))
async def quotes_menu(c, m):
    # If used in a group, you might want to check if the user is an admin first!
    chat_id = m.chat.id
    enabled = await is_enabled(chat_id)
    
    status_text = "✅ ENABLED" if enabled else "❌ DISABLED"
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 Enable", callback_data="enable_module"),
            InlineKeyboardButton("🔴 Disable", callback_data="disable_module")
        ]
    ])
    
    await m.reply(
        f"✨ **Motivational Quotes Module**\n\n"
        f"Current Status in this chat: **{status_text}**\n\n"
        f"If enabled, I will send a powerful memory quote here every hour.",
        reply_markup=kb
    )

@Client.on_callback_query(filters.regex("^(enable_module|disable_module)$"))
async def toggle_module(c, q):
    chat_id = q.message.chat.id
    chat_type = q.message.chat.type.name
    chat_title = q.message.chat.title or q.message.chat.first_name
    
    if q.data == "enable_module":
        await enable_quotes(chat_id, chat_title, chat_type)
        await q.answer("Module Enabled! 🎉", show_alert=True)
    else:
        await disable_quotes(chat_id)
        await q.answer("Module Disabled! ⏸️", show_alert=True)
        
    # Refresh the menu text (Optional, but good UX)
    await quotes_menu(c, q.message)
    await q.message.delete() # Delete old menu
