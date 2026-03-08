from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.automod_db import get_mod_settings, update_mod_settings

def build_mod_menu(chat_id: int, enabled: bool):
    en_txt = "🟢 Auto-Mod: ENABLED" if enabled else "🔴 Auto-Mod: DISABLED"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(en_txt, callback_data=f"mod_tgl_{chat_id}")],
        [InlineKeyboardButton("📊 View Current Stats", callback_data=f"mod_stats_{chat_id}")]
    ])

@Client.on_message(filters.command("modtarget") & filters.private)
async def mod_target_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/modtarget -100123456789`")
        
    try:
        chat_id = int(message.command[1])
        s = await get_mod_settings(chat_id)
        await message.reply(
            f"🛡 **Auto-Mod Dashboard**\n🎯 **Target Group:** `{chat_id}`", 
            reply_markup=build_mod_menu(chat_id, s["enabled"])
        )
    except ValueError:
        await message.reply("❌ Please provide a valid numeric Group ID.")

@Client.on_callback_query(filters.regex(r"^mod_(?P<action>tgl|stats)_(?P<chat_id>-?\d+)$"))
async def mod_callbacks(client, query):
    action = query.matches[0].group("action")
    chat_id = int(query.matches[0].group("chat_id"))
    
    if action == "tgl":
        s = await get_mod_settings(chat_id)
        new_state = not s["enabled"]
        await update_mod_settings(chat_id, enabled=new_state)
        await query.message.edit_reply_markup(reply_markup=build_mod_menu(chat_id, new_state))
        
    elif action == "stats":
        from database import mod_stats
        st = await mod_stats.find_one({"chat_id": chat_id}) or {}
        text = (
            f"📊 **Live Stats for {chat_id}**\n\n"
            f"🔹 Warns Issued: {st.get('warns_issued', 0)}\n"
            f"🔹 Msgs Deleted: {st.get('msgs_deleted', 0)}\n"
            f"🔹 Users Muted: {st.get('users_muted', 0)}\n"
            f"🔹 Warns Decayed: {st.get('warns_decayed', 0)}"
        )
        await query.answer(text, show_alert=True)
