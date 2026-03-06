from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from vgx.database.imdb_db import get_settings, update_settings

def build_settings_menu(chat_id: int, s: dict):
    # Dynamic button text
    en_txt = "🟢 Module Enabled" if s["enabled"] else "🔴 Module Disabled"
    pin_txt = "📌 Pin Post: ON" if s["pin_message"] else "📌 Pin Post: OFF"
    
    # Format intervals & deletes for readability
    int_map = {1: "1m", 5: "5m", 20: "20m", 30: "30m", 60: "1h"}
    del_map = {0: "Off", 30: "30s", 300: "5m", 400: "6.6m", 2400: "40m"}
    
    cur_int = int_map.get(s["interval"], f"{s['interval']}m")
    cur_del = del_map.get(s["auto_delete"], f"{s['auto_delete']}s")
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(en_txt, callback_data=f"imdb_tgl_en_{chat_id}")],
        [InlineKeyboardButton(f"⏱ Interval: {cur_int}", callback_data=f"imdb_cyc_int_{chat_id}"),
         InlineKeyboardButton(f"🗑 Auto-Del: {cur_del}", callback_data=f"imdb_cyc_del_{chat_id}")],
        [InlineKeyboardButton(pin_txt, callback_data=f"imdb_tgl_pin_{chat_id}")],
        [InlineKeyboardButton("📝 Edit Template", callback_data=f"imdb_set_tpl_{chat_id}")]
    ])

@Client.on_message(filters.command("imdbset") & filters.private)
async def imdb_target_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/imdbset -100123456789`")
        
    chat_id = int(message.command[1])
    s = await get_settings(chat_id)
    await message.reply(f"⚙️ **IMDb Settings for** `{chat_id}`", reply_markup=build_settings_menu(chat_id, s))

@Client.on_callback_query(filters.regex(r"^imdb_(?P<action>[a-z_]+)_(?P<chat_id>-?\d+)$"))
async def imdb_callbacks(client, query):
    action = query.matches[0].group("action")
    chat_id = int(query.matches[0].group("chat_id"))
    s = await get_settings(chat_id)
    
    if action == "tgl_en":
        await update_settings(chat_id, enabled=not s["enabled"])
    elif action == "tgl_pin":
        await update_settings(chat_id, pin_message=not s["pin_message"])
        
    elif action == "cyc_int":
        # Cycle through: 1 -> 5 -> 20 -> 30 -> 60 -> 1
        cycles = [1, 5, 20, 30, 60]
        nxt = cycles[(cycles.index(s["interval"]) + 1) % len(cycles)] if s["interval"] in cycles else 1
        await update_settings(chat_id, interval=nxt)
        
    elif action == "cyc_del":
        # Cycle through: 0 -> 30 -> 300 -> 400 -> 2400 -> 0
        cycles = [0, 30, 300, 400, 2400]
        nxt = cycles[(cycles.index(s["auto_delete"]) + 1) % len(cycles)] if s["auto_delete"] in cycles else 0
        await update_settings(chat_id, auto_delete=nxt)
        
    elif action == "set_tpl":
        await query.message.reply(f"📝 **Edit Template for {chat_id}**\nReply with your new template.", reply_markup=ForceReply(selective=True))
        return await query.answer()

    # Refresh UI
    s = await get_settings(chat_id)
    await query.message.edit_reply_markup(reply_markup=build_settings_menu(chat_id, s))

@Client.on_message(filters.private & filters.reply)
async def handle_template_reply(client, message):
    if "Edit Template for" in message.reply_to_message.text:
        chat_id = int(message.reply_to_message.text.split("for ")[1].split("\n")[0])
        await update_settings(chat_id, template=message.text.html)
        await message.reply("✅ Template saved successfully!")
