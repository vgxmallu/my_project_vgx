from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.tag_db import get_user_settings, update_setting

@Client.on_message(filters.command("sets") & filters.private)
async def setttagings_menu(c, m):
    s = await get_user_settings(m.from_user.id)
    if not s:
        return await m.reply("Please send /start first to register!")

    mode_txt = "Complete" if s.get("mode") == "complete" else "Smart"
    mute_txt = "Muted 🔇" if s.get("muted") else "Sound 🔊"

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"Style: {mode_txt}", callback_data="toggle_mode"),
            InlineKeyboardButton(f"Alerts: {mute_txt}", callback_data="toggle_mute")
        ],
        [InlineKeyboardButton("📖 Help & Other Tags", callback_data="help_menu")]
    ])
    
    await m.reply("⚙️ **Your Notification Settings:**", reply_markup=kb)

@Client.on_callback_query(filters.regex("^toggle_"))
async def handle_toggles(c, q):
    user_id = q.from_user.id
    s = await get_user_settings(user_id)
    
    if q.data == "toggle_mode":
        new_mode = "smart" if s.get("mode") == "complete" else "complete"
        await update_setting(user_id, "mode", new_mode)
    elif q.data == "toggle_mute":
        await update_setting(user_id, "muted", not s.get("muted"))
        
    await settings_menu(c, q.message)
    await q.answer("Settings Updated!")
