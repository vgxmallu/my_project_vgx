
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified
from vgx.database.quets_db2 import get_chat_config, update_config

# Helper function to generate the dynamic menu
def generate_menu(s):
    status = "🟢 ON" if s["enabled"] else "🔴 OFF"
    pin = "✅ ON" if s["pin"] else "❌ OFF"
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏱ Frequency", callback_data="menu_time"),
         InlineKeyboardButton("🗑 Auto-Delete", callback_data="menu_del")],
        [InlineKeyboardButton(f"📌 Pin Mode: {pin}", callback_data="toggle_pin"),
         InlineKeyboardButton(f"🔄 Module: {status}", callback_data="toggle_mod")],
        [InlineKeyboardButton("🗑 Delete Last Sent Message", callback_data="del_last")]
    ])
    return kb

@Client.on_message(filters.command("quotes"))
async def open_settings(c, m):
    s = await get_chat_config(m.chat.id)
    text = (
        "✨ **Golden Quotes Configuration**\n\n"
        f"**Target:** `{m.chat.title or 'Private'}`\n"
        f"**Frequency:** Every {s['interval']}m\n"
        f"**Auto-Delete:** {f'{s['delete_after']}s' if s['delete_after'] > 0 else 'Off'}"
    )
    await m.reply(text, reply_markup=generate_menu(s))

@Client.on_callback_query(filters.regex("^menu_"))
async def sub_menus(c, q):
    if q.data == "menu_time":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("1m", callback_data="time_1"), InlineKeyboardButton("5m", callback_data="time_5")],
            [InlineKeyboardButton("20m", callback_data="time_20"), InlineKeyboardButton("30m", callback_data="time_30")],
            [InlineKeyboardButton("1h", callback_data="time_60"), InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ])
        await q.edit_message_text("⏰ **Select Message Interval:**", reply_markup=kb)
        
    elif q.data == "menu_del":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("30s", callback_data="del_30"), InlineKeyboardButton("300s", callback_data="del_300")],
            [InlineKeyboardButton("400s", callback_data="del_400"), InlineKeyboardButton("2400s", callback_data="del_2400")],
            [InlineKeyboardButton("❌ Disable", callback_data="del_0"), InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ])
        await q.edit_message_text("🗑 **Select Auto-Delete Time:**", reply_markup=kb)

@Client.on_callback_query(filters.regex("^(time_|del_|toggle_|back_main|del_last)"))
async def process_settings(c, q):
    chat_id = q.message.chat.id
    data = q.data
    s = await get_chat_config(chat_id)

    # 1. Handle "Delete Last Message"
    if data == "del_last":
        if s.get("last_msg_id"):
            try:
                await c.delete_messages(chat_id, s["last_msg_id"])
                await q.answer("🗑 Last message deleted!")
            except:
                await q.answer("❌ Message not found. (Already deleted?)", show_alert=True)
        else:
            await q.answer("No message history recorded.", show_alert=True)
        return

    # 2. Handle Settings Toggles
    if data.startswith("time_"):
        await update_config(chat_id, interval=int(data.split("_")[1]))
    elif data.startswith("del_"):
        await update_config(chat_id, delete_after=int(data.split("_")[1]))
    elif data == "toggle_pin":
        await update_config(chat_id, pin=not s["pin"])
    elif data == "toggle_mod":
        await update_config(chat_id, enabled=not s["enabled"])

    # 3. Reload settings and update the menu UI
    s = await get_chat_config(chat_id)
    try:
        await q.message.edit_text(
            f"✨ **Golden Quotes Configuration**\n\n"
            f"**Frequency:** Every {s['interval']}m\n"
            f"**Auto-Delete:** {f'{s['delete_after']}s' if s['delete_after'] > 0 else 'Off'}", 
            reply_markup=generate_menu(s)
        )
    except MessageNotModified:
        pass # Catch the error so the bot doesn't crash if buttons look the same
    
    await q.answer("Settings Updated!")
