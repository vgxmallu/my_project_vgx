from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.sleepmod_db import get_nw_settings, update_nw_settings

def build_nw_keyboard(chat_id: int, s: dict):
    en_txt = "🟢 Nightwatch: ENABLED" if s["enabled"] else "🔴 Nightwatch: DISABLED"
    mode_txt = "🛡 Current Mode: STRICT" if s["current_mode"] == "strict" else "☀️ Current Mode: LENIENT"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(en_txt, callback_data=f"nw_tgl_{chat_id}")],
        [InlineKeyboardButton(mode_txt, callback_data="nw_dummy")] # Dummy button just for display
    ])

@Client.on_message(filters.command("nighttarget") & filters.private)
async def night_target_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/nighttarget -100123456789`")
        
    try:
        chat_id = int(message.command[1])
        s = await get_nw_settings(chat_id)
        
        text = (
            "🦉 **Nightwatch Security Engine**\n\n"
            "This module automatically shifts the group's security posture based on the time of day.\n\n"
            "☀️ **Day (07:00 - 01:00):** Lenient (Allows media/videos, blocks crypto spam)\n"
            "🛡 **Night (01:00 - 07:00):** Strict (Blocks ALL links, media, forwards, and enables extreme flood control)\n\n"
            f"**Target Chat:** `{chat_id}`"
        )
        
        await message.reply(text, reply_markup=build_nw_keyboard(chat_id, s))
    except ValueError:
        await message.reply("❌ Please provide a valid numeric Group ID.")

@Client.on_callback_query(filters.regex(r"^nw_(?P<action>tgl)_(?P<chat_id>-?\d+)$"))
async def nw_callbacks(client, query):
    action = query.matches[0].group("action")
    chat_id = int(query.matches[0].group("chat_id"))
    
    if action == "tgl":
        s = await get_nw_settings(chat_id)
        new_state = not s["enabled"]
        await update_nw_settings(chat_id, enabled=new_state)
        
        # Refresh UI
        s["enabled"] = new_state
        await query.message.edit_reply_markup(reply_markup=build_nw_keyboard(chat_id, s))
        await query.answer(f"Nightwatch {'Enabled' if new_state else 'Disabled'}!")
