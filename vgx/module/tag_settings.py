from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.tag_db import get_user_settings, update_setting

@Client.on_message(filters.command("settings"))
async def settings_menu(c, m):
    s = await get_user_settings(m.from_user.id)
    
    mode_text = "🟢 Complete" if s["mode"] == "complete" else "🟡 Smart"
    mute_text = "🔇 Muted" if s["muted"] else "🔊 Unmuted"
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"Mode: {s['mode'].capitalize()}", callback_data="toggle_mode", style="primary"),
            InlineKeyboardButton(f"Status: {mute_text}", callback_data="toggle_mute", style="danger" if s["muted"] else "success")
        ],
        [InlineKeyboardButton("📖 Help / Other Tags", callback_data="help_tags")]
    ])
    
    await m.reply("⚙️ **Notification Settings**\nConfigure how you receive alerts below:", reply_markup=kb)

@Client.on_callback_query(filters.regex("^toggle_"))
async def handle_settings(c, q):
    user_id = q.from_user.id
    s = await get_user_settings(user_id)
    
    if q.data == "toggle_mode":
        new_mode = "smart" if s["mode"] == "complete" else "complete"
        await update_setting(user_id, "mode", new_mode)
    
    elif q.data == "toggle_mute":
        await update_setting(user_id, "muted", not s["muted"])
    
    # Refresh the menu
    await settings_menu(c, q.message)
    await q.answer("Setting Updated!")
