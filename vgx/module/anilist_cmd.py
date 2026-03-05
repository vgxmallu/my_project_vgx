import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified
from pyrogram.enums import ChatMemberStatus
from vgx.database.anilist_db import get_chat, update_chat
from pyrogram.enums import ButtonStyle
# --- 1. Security Check ---
async def is_user_admin(client, target_id: int, user_id: int) -> bool:
    if target_id == user_id: return True
    try:
        member = await client.get_chat_member(target_id, user_id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except:
        return False

# --- 2. Keyboard Builders ---
def build_main_menu(chat_id: int, s: dict):
    btn_mod = "🟢 Status: ON" if s.get("enabled", False) else "🔴 Status: OFF"
    btn_pin = "📌 Pin: ON" if s.get("pin", False) else "📌 Pin: OFF"
    
    return InlineKeyboardMarkup([[
         InlineKeyboardButton(btn_mod, callback_data=f"tgl1_mod_{chat_id}", style=ButtonStyle.PRIMARY),
         InlineKeyboardButton(btn_pin, callback_data=f"tgl1_pin_{chat_id}", style=ButtonStyle.PRIMARY)
       ],[
         InlineKeyboardButton("⏱ Set Interval", callback_data=f"nav1_int_{chat_id}", style=ButtonStyle.PRIMARY),
         InlineKeyboardButton("🗑 Auto-Delete", callback_data=f"nav1_del_{chat_id}", style=ButtonStyle.PRIMARY)
       ],[
         InlineKeyboardButton("❌ Cancel", callback_data="wiz_cancel", style=ButtonStyle.DANGER)
       ]]
    )

def build_sub_menu(chat_id: int, menu_type: str):
    if menu_type == "int":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("1m", callback_data=f"set1_int_1_{chat_id}", style=ButtonStyle.PRIMARY), InlineKeyboardButton("5m", callback_data=f"set1_int_5_{chat_id}", style=ButtonStyle.PRIMARY)],
            [InlineKeyboardButton("20m", callback_data=f"set1_int_20_{chat_id}", style=ButtonStyle.PRIMARY), InlineKeyboardButton("30m", callback_data=f"set1_int_30_{chat_id}", style=ButtonStyle.PRIMARY)],
            [InlineKeyboardButton("1h", callback_data=f"set1_int_60_{chat_id}", style=ButtonStyle.PRIMARY), InlineKeyboardButton("🔙 Back", callback_data=f"nav1_maine_{chat_id}", style=ButtonStyle.PRIMARY)]
        ])
    elif menu_type == "del":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("30s", callback_data=f"set1_del_30_{chat_id}"), InlineKeyboardButton("300s", callback_data=f"set1_del_300_{chat_id}")],
            [InlineKeyboardButton("400s", callback_data=f"set1_del_400_{chat_id}"), InlineKeyboardButton("2400s", callback_data=f"set1_del_2400_{chat_id}")],
            [InlineKeyboardButton("❌ Off", callback_data=f"set1_del_0_{chat_id}", style=ButtonStyle.DANGER), InlineKeyboardButton("🔙 Back", callback_data=f"nav1_maine_{chat_id}")]
        ])

async def refresh_ui(query, chat_id: int):
    s = await get_chat(chat_id)
    del_val = s.get("delete_after", 0)
    del_str = f"{del_val}s" if del_val > 0 else "Off"
    inv_stamp = f" \u200b" * int(time.time() % 3)
    
    text = (
        "⛩️ **Anime Scheduler Panel**\n"
        f"🎯 **Target:** `{chat_id}`{inv_stamp}\n\n"
        f"**Frequency:** Every {s.get('interval', 60)}m\n"
        f"**Auto-Delete:** {del_str}"
    )
    try:
        await query.message.edit_text(text, reply_markup=build_main_menu(chat_id, s))
    except MessageNotModified:
        pass

# --- 3. The Command ---
@Client.on_message(filters.command(["setanime", "anime"]))
async def open_panel(client, message):
    target_id = message.chat.id
    if len(message.command) > 1:
        try: target_id = int(message.command[1])
        except ValueError: return await message.reply("❌ Invalid Chat ID.")

    if str(target_id).startswith("-"):
        if not await is_user_admin(client, target_id, message.from_user.id):
            return await message.reply("❌ **Access Denied:** You must be an Admin of the target group.")

    s = await get_chat(target_id)
    del_val = s.get("delete_after", 0)
    text = (
        "⛩️ **Anime Scheduler Panel**\n"
        f"🎯 **Target:** `{target_id}`\n\n"
        f"**Frequency:** Every {s.get('interval', 60)}m\n"
        f"**Auto-Delete:** {f'{del_val}s' if del_val > 0 else 'Off'}"
    )
    await message.reply(text, reply_markup=build_main_menu(target_id, s))



@Client.on_callback_query(filters.regex(r"^(?P<action>tgl1|nav1|set1|cmd1)_(?P<param>[a-z]+)(?:_(?P<val>\d+))?_(?P<chat_id>-?\d+)$"))
async def module1_callback_router(client, query):
    action = query.matches[0].group("action")
    param = query.matches[0].group("param")
    val_raw = query.matches[0].group("val")
    chat_id = int(query.matches[0].group("chat_id"))
    
    # ✅ THE BULLETPROOF FIX: Safely convert to integer ONLY if val_raw isn't None
    val = int(val_raw) if val_raw is not None else None
    
    # Check Permissions
    if not await is_user_admin(client, chat_id, query.from_user.id):
        return await query.answer("❌ Admin strictly required.", show_alert=True)
        
    s = await get_chat(chat_id)

    # Route based on the exact action matched
    if action == "tgl1":
        if param == "mod": await update_chat(chat_id, enabled=not s.get("enabled", False))
        elif param == "pin": await update_chat(chat_id, pin=not s.get("pin", False))
        await refresh_ui(query, chat_id)
        
    elif action == "nav1":
        if param == "maine": 
            await refresh_ui(query, chat_id)
        else: 
            await query.edit_message_text(
                f"🎯 Target: `{chat_id}`\n⚙️ Select Option:", 
                reply_markup=build_sub_menu(chat_id, param)
            )
        
    elif action == "set1":
        # Since 'val' is now safely handled above, we can just use it directly here
        if param == "int": await update_chat(chat_id, interval=val)
        elif param == "del": await update_chat(chat_id, delete_after=val)
        await query.answer("Settings Saved!")
        await refresh_ui(query, chat_id)
        
    elif action == "cmd1" and param == "del":
        last_id = s.get("last_msg_id")
        if last_id:
            try:
                await client.delete_messages(chat_id, last_id)
                await query.answer("🗑 Last Message deleted!", show_alert=True)
            except:
                await query.answer("❌ Message missing or lack permissions.", show_alert=True)
        else: 
            await query.answer("⚠️ No history found.", show_alert=True)

"""
# --- 4. Callbacks via Strict Regex ---
@Client.on_callback_query(filters.regex(r"^(?P<action>tgl1|nav1|set1|cmd1)_(?P<param>\w+)_?(?P<val>\d+)?_(?P<chat_id>-?\d+)$"))
async def core_callback_router(client, query):
    action = query.matches[0].group("action")
    param = query.matches[0].group("param")
    val_raw = query.matches[0].group("val")
    chat_id = int(query.matches[0].group("chat_id"))
    
    # Check Permissions
    if not await is_user_admin(client, chat_id, query.from_user.id):
        return await query.answer("❌ Admin strictly required.", show_alert=True)
        
    s = await get_chat(chat_id)

    # Route based on action prefix
    if action == "tgl1":
        if param == "mod1": await update_chat(chat_id, enabled=not s.get("enabled", False))
        elif param == "pin": await update_chat(chat_id, pin=not s.get("pin", False))
        await refresh_ui(query, chat_id)
        
    elif action == "nav1":
        if param == "main1": await refresh_ui(query, chat_id)
        else: await query.edit_message_text(f"🎯 Target: `{chat_id}`\n⚙️ Select Option:", reply_markup=build_sub_menu(chat_id, param))
        
    elif action == "set1":
        val = int(val_raw)
        if param == "int1": await update_chat(chat_id, interval=val)
        elif param == "del1": await update_chat(chat_id, delete_after=val)
        await query.answer("Settings Saved!")
        await refresh_ui(query, chat_id)
        
    elif action == "cmd1" and param == "del":
        last_id = s.get("last_msg_id")
        if last_id:
            try:
                await client.delete_messages(chat_id, last_id)
                await query.answer("🗑 Last Anime deleted!", show_alert=True)
            except:
                await query.answer("❌ Message missing or lack permissions.", show_alert=True)
        else: await query.answer("⚠️ No history found.", show_alert=True)
"""
