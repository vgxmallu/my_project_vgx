from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.tag_db import get_user_config, update_config

@Client.on_message(filters.command("setag"))
async def settings_panel(c, m):
    s = await get_user_config(m.from_user.id)
    
    mode_label = "Complete ✅" if s["mode"] == "complete" else "Smart 💡"
    mute_label = "Muted 🔇" if s["muted"] else "Sound 🔊"
    
    # Standard buttons as requested
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"Style: {mode_label}", callback_data="set_style"),
            InlineKeyboardButton(f"Alerts: {mute_label}", callback_data="set_mute")
        ],
        [InlineKeyboardButton("❓ Help & Other Tags", callback_data="help_others")]
    ])
    
    await m.reply(
        "⚙️ **Notification Center Settings**\n"
        "Configure how you receive your group alerts below:", 
        reply_markup=kb
    )

@Client.on_callback_query(filters.regex("^set_"))
async def update_settings(c, q):
    user_id = q.from_user.id
    s = await get_user_config(user_id)
    
    if q.data == "set_style":
        new_val = "smart" if s["mode"] == "complete" else "complete"
        await update_config(user_id, "mode", new_val)
    elif q.data == "set_mute":
        await update_config(user_id, "muted", not s["muted"])
        
    await settings_panel(c, q.message) # Refresh menu
    await q.answer("Updated!")
