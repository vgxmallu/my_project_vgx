from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from vgx.database.imdb_db import get_settings, update_settings

def build_settings_menu(chat_id: int, s: dict):
    # 1. Safely extract ALL settings with defaults to prevent KeyErrors
    is_enabled = s.get("enabled", False)
    is_pinned = s.get("pin_message", False)
    interval_val = s.get("interval", 30)
    auto_del_val = s.get("auto_delete", 0)

    # 2. Dynamic button text
    en_txt = "🟢 Module Enabled" if is_enabled else "🔴 Module Disabled"
    pin_txt = "📌 Pin Post: ON" if is_pinned else "📌 Pin Post: OFF"
    
    # 3. Format intervals & deletes for readability
    int_map = {1: "1m", 5: "5m", 20: "20m", 30: "30m", 60: "1h"}
    del_map = {0: "Off", 30: "30s", 300: "5m", 400: "6.6m", 2400: "40m"}

    cur_int = int_map.get(interval_val, f"{interval_val}m")
    cur_del = del_map.get(auto_del_val, f"{auto_del_val}s") # NameError fixed here!

    # 4. Return the keyboard
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
    
    # Safely handle toggles
    if action == "tgl_en":
        await update_settings(chat_id, enabled=not s.get("enabled", False))
        
    elif action == "tgl_pin":
        await update_settings(chat_id, pin_message=not s.get("pin_message", False))
        
    # Safely handle interval cycling
    elif action == "cyc_int":
        cycles = [1, 5, 20, 30, 60]
        current_int = s.get("interval", 30)
        
        if current_int in cycles:
            nxt = cycles[(cycles.index(current_int) + 1) % len(cycles)]
        else:
            nxt = 1 # Fallback if they somehow have a weird custom interval
            
        await update_settings(chat_id, interval=nxt)
        
    # Safely handle auto-delete cycling
    elif action == "cyc_del":
        cycles = [0, 30, 300, 400, 2400]
        current_del = s.get("auto_delete", 0)
        
        if current_del in cycles:
            nxt = cycles[(cycles.index(current_del) + 1) % len(cycles)]
        else:
            nxt = 0 # Fallback if they have a weird custom delete timer
            
        await update_settings(chat_id, auto_delete=nxt)
        
    elif action == "set_tpl":
        await query.message.reply(
            f"📝 **Edit Template for {chat_id}**\nReply with your new template.", 
            reply_markup=ForceReply(selective=True)
        )
        return await query.answer()

    # Refresh UI safely
    s = await get_settings(chat_id)
    await query.message.edit_reply_markup(reply_markup=build_settings_menu(chat_id, s))

@Client.on_message(filters.private & filters.reply)
async def handle_template_reply(client, message):
    if "Edit Template for" in message.reply_to_message.text:
        chat_id = int(message.reply_to_message.text.split("for ")[1].split("\n")[0])
        await update_settings(chat_id, template=message.text.html)
        await message.reply("✅ Template saved successfully!")
