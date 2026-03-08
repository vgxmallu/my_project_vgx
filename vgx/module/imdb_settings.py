from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from vgx.database.imdb_db import get_target, update_target

def build_menu(chat_id: int, s: dict):
    # Text Formatting
    en_txt = "🟢 Scheduler: ON" if s["enabled"] else "🔴 Scheduler: OFF"
    pin_txt = "📌 Auto-Pin: ON" if s["pin"] else "📌 Auto-Pin: OFF"
    
    # Maps for clean display
    i_map = {1: "1m", 5: "5m", 20: "20m", 30: "30m", 60: "1h"}
    d_map = {0: "Off", 30: "30s", 300: "5m", 400: "6.6m", 2400: "40m"}
    
    cur_int = i_map.get(s["interval"], f"{s['interval']}m")
    cur_del = d_map.get(s["auto_delete"], f"{s['auto_delete']}s")
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(en_txt, callback_data=f"set_en_{chat_id}")],
        [InlineKeyboardButton(f"⏱ Interval: {cur_int}", callback_data=f"set_int_{chat_id}"),
         InlineKeyboardButton(f"🗑 Auto-Del: {cur_del}", callback_data=f"set_del_{chat_id}")],
        [InlineKeyboardButton(pin_txt, callback_data=f"set_pin_{chat_id}")],
        [InlineKeyboardButton("📝 Edit Template", callback_data=f"set_tpl_{chat_id}")]
    ])

# --- Main Target Command ---
@Client.on_message(filters.command("imdbtarget") & filters.private)
async def target_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/imdbtarget -100123456789`")
        
    try:
        chat_id = int(message.command[1])
        s = await get_target(chat_id)
        await message.reply(f"🍿 **IMDb Random Scheduler**\n🎯 **Target:** `{chat_id}`", reply_markup=build_menu(chat_id, s))
    except ValueError:
        await message.reply("❌ Please provide a valid numeric Group ID.")

# --- Regex Callback Logic ---
@Client.on_callback_query(filters.regex(r"^set_(?P<action>en|int|del|pin|tpl)_(?P<chat_id>-?\d+)$"))
async def settings_callbacks(client, query):
    action = query.matches[0].group("action")
    chat_id = int(query.matches[0].group("chat_id"))
    s = await get_target(chat_id)
    
    if action == "en":
        await update_target(chat_id, enabled=not s["enabled"])
    elif action == "pin":
        await update_target(chat_id, pin=not s["pin"])
    elif action == "int":
        # Cycle through: 1 -> 5 -> 20 -> 30 -> 60 -> 1
        cycles = [1, 5, 20, 30, 60]
        nxt = cycles[(cycles.index(s["interval"]) + 1) % len(cycles)] if s["interval"] in cycles else 1
        await update_target(chat_id, interval=nxt)
    elif action == "del":
        # Cycle through: 0 -> 30 -> 300 -> 400 -> 2400 -> 0
        cycles = [0, 30, 300, 400, 2400]
        nxt = cycles[(cycles.index(s["auto_delete"]) + 1) % len(cycles)] if s["auto_delete"] in cycles else 0
        await update_target(chat_id, auto_delete=nxt)
    elif action == "tpl":
        await query.message.reply(
            f"📝 **Editing Template for {chat_id}**\nReply to this message with your new template.",
            reply_markup=ForceReply(selective=True)
        )
        return await query.answer()

    # Refresh Menu
    s = await get_target(chat_id)
    await query.message.edit_reply_markup(reply_markup=build_menu(chat_id, s))

# --- Handle Forced Reply for Template ---
@Client.on_message(filters.private & filters.reply)
async def save_template(client, message):
    if message.reply_to_message and "Editing Template for" in message.reply_to_message.text:
        chat_id = int(message.reply_to_message.text.split("for ")[1].split("\n")[0])
        await update_target(chat_id, template=message.text.html)
        await message.reply("✅ **Custom Template Saved Successfully!**")
