import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified
from vgx.database.quets_db2 import get_chat, update_chat
from vgx.utils.admins import is_user_admin

    

# --- UI Keyboard Generators ---
def build_main_menu(chat_id: int, s: dict):
    # ✅ SAFELY fetch the boolean values, defaulting to False if missing
    is_enabled = s.get("enabled", False)
    is_pinned = s.get("pin", False)
    
    state_btn = "🟢 Status: ON" if is_enabled else "🔴 Status: OFF"
    pin_btn = "📌 Pin: ON" if is_pinned else "📌 Pin: OFF"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(state_btn, callback_data=f"tgl_mod_{chat_id}"),
         InlineKeyboardButton(pin_btn, callback_data=f"tgl_pin_{chat_id}")],
        [InlineKeyboardButton("⏱ Set Interval", callback_data=f"nav_int_{chat_id}"),
         InlineKeyboardButton("🗑 Set Auto-Delete", callback_data=f"nav_del_{chat_id}")],
        [InlineKeyboardButton("🗑 Delete Last Sent Quote", callback_data=f"cmd_del_last_{chat_id}")]
    ])

def build_interval_menu(chat_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1m", callback_data=f"set_int_1_{chat_id}"), InlineKeyboardButton("5m", callback_data=f"set_int_5_{chat_id}")],
        [InlineKeyboardButton("20m", callback_data=f"set_int_20_{chat_id}"), InlineKeyboardButton("30m", callback_data=f"set_int_30_{chat_id}")],
        [InlineKeyboardButton("1h", callback_data=f"set_int_60_{chat_id}"), InlineKeyboardButton("🔙 Back", callback_data=f"nav_main_{chat_id}")]
    ])

def build_delete_menu(chat_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("30s", callback_data=f"set_del_30_{chat_id}"), InlineKeyboardButton("300s", callback_data=f"set_del_300_{chat_id}")],
        [InlineKeyboardButton("400s", callback_data=f"set_del_400_{chat_id}"), InlineKeyboardButton("2400s", callback_data=f"set_del_2400_{chat_id}")],
        [InlineKeyboardButton("❌ Disable", callback_data=f"set_del_0_{chat_id}"), InlineKeyboardButton("🔙 Back", callback_data=f"nav_main_{chat_id}")]
    ])

async def refresh_main_ui(query, chat_id: int):
    """Safely refreshes the main UI without crashing on MessageNotModified."""
    s = await get_chat(chat_id)
    del_str = f"{s['delete_after']}s" if s['delete_after'] > 0 else "Off"
    inv_stamp = f" \u200b" * int(time.time() % 3) # Zero-width space trick
    
    text = (
        "⚙️ **Quotes Control Panel**\n"
        f"🎯 **Target:** `{chat_id}`{inv_stamp}\n\n"
        f"**Frequency:** Every {s['interval']}m\n"
        f"**Auto-Delete:** {del_str}"
    )
    try:
        await query.message.edit_text(text, reply_markup=build_main_menu(chat_id, s))
    except MessageNotModified:
        pass


@Client.on_message(filters.command("setquote"))
async def open_pabssnnel(client, message):
    target_id = message.chat.id
    
    # Target feature: /setquote -100123456789
    if len(message.command) > 1:
        try:
            target_id = int(message.command[1])
        except ValueError:
            return await message.reply("❌ Invalid Chat ID. Provide a valid number.")

    # 🔒 SECURITY CHECK: Are they an admin of the target group?
    # We only check if the target is a group/supergroup, private PMs are fine.
    if str(target_id).startswith("-100") or str(target_id).startswith("-"):
        if not await is_user_admin(client, target_id, message.from_user.id):
            return await message.reply("❌ **Access Denied:** Only group admins can configure quotes.")


    s = await get_chat(target_id)
    # ✅ SAFELY fetch values with .get() to prevent KeyError on old database entries
    interval_val = s.get('interval', 60) 
    delete_val = s.get('delete_after', 0)
    
    del_str = f"{delete_val}s" if delete_val > 0 else "Off"
    
    text = (
        "⚙️ **Quotes Control Panel**\n"
        f"🎯 **Target:** `{target_id}`\n\n"
        f"**Frequency:** Every {interval_val}m\n"
        f"**Auto-Delete:** {del_str}"
    )
    
    await message.reply(text, reply_markup=build_main_menu(target_id, s))


@Client.on_callback_query(filters.regex(r"^tgl_(?P<setting>mod|pin)_(?P<chat_id>-?\d+)$"))
async def handle_toggles(client, query):
    setting = query.matches[0].group("setting")
    chat_id = int(query.matches[0].group("chat_id"))
    s = await get_chat(chat_id)
    
    if setting == "mod":
        await update_chat(chat_id, enabled=not s["enabled"])
    elif setting == "pin":
        await update_chat(chat_id, pin=not s["pin"])
        
    await refresh_main_ui(query, chat_id)
    await query.answer("Toggled successfully!")

# --- 2. Navigation Regex Callbacks ---
@Client.on_callback_query(filters.regex(r"^nav_(?P<menu>main|int|del)_(?P<chat_id>-?\d+)$"))
async def handle_navigation(client, query):
    
    menu = query.matches[0].group("menu")
    chat_id = int(query.matches[0].group("chat_id"))
    
    if menu == "main":
        await refresh_main_ui(query, chat_id)
    elif menu == "int":
        await query.edit_message_text(f"🎯 **Target:** `{chat_id}`\n⏰ **Select Interval:**", reply_markup=build_interval_menu(chat_id))
    elif menu == "del":
        await query.edit_message_text(f"🎯 **Target:** `{chat_id}`\n🗑 **Select Auto-Delete Time:**", reply_markup=build_delete_menu(chat_id))


@Client.on_callback_query(filters.regex(r"^tgl_(?P<setting>mod|pin)_(?P<chat_id>-?\d+)$"))
async def handle_toggles(client, query):

    setting = query.matches[0].group("setting")
    chat_id = int(query.matches[0].group("chat_id"))
    s = await get_chat(chat_id)
    
    # ✅ SAFELY get the current values before flipping them
    if setting == "mod":
        current_status = s.get("enabled", False)
        await update_chat(chat_id, enabled=not current_status)
        
    elif setting == "pin":
        current_pin = s.get("pin", False)
        await update_chat(chat_id, pin=not current_pin)
        
    await refresh_main_ui(query, chat_id)
    await query.answer("Toggled successfully!")


# --- 4. Setter Regex Callbacks ---
@Client.on_callback_query(filters.regex(r"^set_(?P<type>int|del)_(?P<val>\d+)_(?P<chat_id>-?\d+)$"))
async def handle_setters(client, query):
    
    setting_type = query.matches[0].group("type")
    val = int(query.matches[0].group("val"))
    chat_id = int(query.matches[0].group("chat_id"))
    
    if setting_type == "int":
        await update_chat(chat_id, interval=val)
        await query.answer(f"Interval updated to {val}m")
    elif setting_type == "del":
        await update_chat(chat_id, delete_after=val)
        await query.answer(f"Auto-Delete updated to {val}s")
        
    await refresh_main_ui(query, chat_id)

# --- 5. Action Regex Callbacks ---
@Client.on_callback_query(filters.regex(r"^cmd_del_last_(?P<chat_id>-?\d+)$"))
async def handle_delete_last(client, query):
    
    chat_id = int(query.matches[0].group("chat_id"))
    s = await get_chat(chat_id)
    
    if s.get("last_msg_id"):
        try:
            await client.delete_messages(chat_id, s["last_msg_id"])
            await query.answer("✅ Last quote deleted!", show_alert=True)
        except Exception:
            await query.answer("❌ Message not found or lacking delete permissions.", show_alert=True)
    else:
        await query.answer("⚠️ No message history found.", show_alert=True)
