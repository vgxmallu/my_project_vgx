from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.quets_db2 import get_chat_data, update_chat

@Client.on_message(filters.command("set_quotes"))
async def main_mffenu(c, m):
    s = await get_chat_data(m.chat.id)
    
    status = "🟢 Enabled" if s["enabled"] else "🔴 Disabled"
    text = (
        "✨ **Golden Hour Settings**\n\n"
        f"**Target Chat:** `{m.chat.title or 'Private'}`\n"
        f"**Status:** {status}\n"
        f"**Interval:** {s['interval']}m | **Auto-Delete:** {s['delete_after']}s\n"
        f"**Pin Mode:** {'✅ On' if s['pin'] else '❌ Off'}"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏱ Interval", callback_data="menu_time"),
         InlineKeyboardButton("🗑 Auto-Delete", callback_data="menu_del")],
        [InlineKeyboardButton("📌 Toggle Pin", callback_data="toggle_pin"),
         InlineKeyboardButton("🔄 Toggle Module", callback_data="toggle_mod")],
        [InlineKeyboardButton("🗑 Delete Last Sent", callback_data="del_last")]
    ])
    await m.reply(text, reply_markup=kb)

@Client.on_callback_query(filters.regex("^menu_"))
async def sub_menus(c, q):
    if q.data == "menu_time":
        buttons = [
            [InlineKeyboardButton("1m", callback_data="set_int_1"), InlineKeyboardButton("5m", callback_data="set_int_5")],
            [InlineKeyboardButton("20m", callback_data="set_int_20"), InlineKeyboardButton("30m", callback_data="set_int_30")],
            [InlineKeyboardButton("1h", callback_data="set_int_60"), InlineKeyboardButton("🔙 Back", callback_data="menu_main")]
        ]
        await q.edit_message_text("⏰ **Select Message Interval:**", reply_markup=InlineKeyboardMarkup(buttons))
    
    elif q.data == "menu_del":
        buttons = [
            [InlineKeyboardButton("30s", callback_data="set_del_30"), InlineKeyboardButton("300s", callback_data="set_del_300")],
            [InlineKeyboardButton("400s", callback_data="set_del_400"), InlineKeyboardButton("2400s", callback_data="set_del_2400")],
            [InlineKeyboardButton("❌ Off", callback_data="set_del_0"), InlineKeyboardButton("🔙 Back", callback_data="menu_main")]
        ]
        await q.edit_message_text("🗑 **Select Auto-Delete Time:**", reply_markup=InlineKeyboardMarkup(buttons))
