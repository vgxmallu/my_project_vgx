import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus
from vgx.database.service_cleaner_db import get_cleaner_settings, update_cleaner_settings

# --- Security Check ---
async def is_admin(client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except:
        return False

# --- UI Builder (Now with Select All logic) ---
def build_cleaner_menu(chat_id: int, s: dict):
    def btn_txt(name, key):
        return f"🟢 {name}" if s.get(key) else f"🔴 {name}"
        
    # Check if every single option is currently True
    all_enabled = all([
        s.get("del_joins"), s.get("del_leaves"), 
        s.get("del_vc"), s.get("del_pins"), s.get("del_info")
    ])
    
    # Dynamic text for the Select All button
    toggle_all_text = "🔴 Disable All" if all_enabled else "🟢 Enable All"
        
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_txt("Joins", "del_joins"), callback_data=f"cln_tgl_joins_{chat_id}"),
         InlineKeyboardButton(btn_txt("Leaves", "del_leaves"), callback_data=f"cln_tgl_leaves_{chat_id}")],
        [InlineKeyboardButton(btn_txt("Voice Chats", "del_vc"), callback_data=f"cln_tgl_vc_{chat_id}"),
         InlineKeyboardButton(btn_txt("Pinned Msgs", "del_pins"), callback_data=f"cln_tgl_pins_{chat_id}")],
        [InlineKeyboardButton(btn_txt("Photo/Title Changes", "del_info"), callback_data=f"cln_tgl_info_{chat_id}")],
        # The new Master Toggle Button
        [InlineKeyboardButton(toggle_all_text, callback_data=f"cln_tgl_all_{chat_id}")]
    ])

async def refresh_cleaner_menu(query, chat_id: int):
    s = await get_cleaner_settings(chat_id)
    inv_stamp = f" \u200b" * int(time.time() % 3)
    text = (
        "🧹 **Service Message Cleaner**\n"
        f"🎯 **Target:** `{chat_id}`{inv_stamp}\n\n"
        "Select which system messages I should automatically delete from the chat:"
    )
    try:
        await query.message.edit_text(text, reply_markup=build_cleaner_menu(chat_id, s))
    except Exception:
        pass

# --- Command ---
@Client.on_message(filters.command(["cleaner", "service"]) & filters.group)
async def cleaner_cmd(client, message):
    chat_id = message.chat.id
    if not await is_admin(client, chat_id, message.from_user.id):
        return await message.reply("❌ Only admins can configure the cleaner.")
        
    s = await get_cleaner_settings(chat_id)
    text = (
        "🧹 **Service Message Cleaner**\n"
        f"🎯 **Target:** `{chat_id}`\n\n"
        "Select which system messages I should automatically delete from the chat:"
    )
    await message.reply(text, reply_markup=build_cleaner_menu(chat_id, s))

# --- Callbacks (Updated to handle "all") ---
@Client.on_callback_query(filters.regex(r"^cln_tgl_(?P<setting>[a-z_]+)_(?P<chat_id>-?\d+)$"))
async def cleaner_callbacks(client, query):
    setting = query.matches[0].group("setting")
    chat_id = int(query.matches[0].group("chat_id"))
    
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("❌ Admin strictly required.", show_alert=True)
        
    s = await get_cleaner_settings(chat_id)
    
    # --- 1. Master Toggle Logic ---
    if setting == "all":
        # Check current state: If all are true, turn them false. Otherwise, turn them all true.
        all_enabled = all([s.get("del_joins"), s.get("del_leaves"), s.get("del_vc"), s.get("del_pins"), s.get("del_info")])
        new_state = not all_enabled
        
        # Update MongoDB with the new state for ALL keys at once
        await update_cleaner_settings(
            chat_id, 
            del_joins=new_state, 
            del_leaves=new_state, 
            del_vc=new_state, 
            del_pins=new_state, 
            del_info=new_state
        )
        
    # --- 2. Individual Button Logic ---
    else:
        db_key = f"del_{setting}" 
        new_value = not s.get(db_key, False)
        await update_cleaner_settings(chat_id, **{db_key: new_value})
    
    # Refresh UI
    await refresh_cleaner_menu(query, chat_id)
 

@Client.on_message(filters.service & filters.group)
async def handle_service_messages(client, message):
    chat_id = message.chat.id
    s = await get_cleaner_settings(chat_id)
    
    try:
        # 1. User Joins (Also catches users joining via invite links)
        if message.new_chat_members and s.get("del_joins", False):
            await message.delete()
            
        # 2. User Leaves
        elif message.left_chat_member and s.get("del_leaves", False):
            await message.delete()
            
        # 3. Voice Chats (Started, Ended, or Members Invited)
        elif (message.video_chat_started or message.video_chat_ended or message.video_chat_members_invited) and s.get("del_vc", False):
            await message.delete()
            
        # 4. Pinned Messages ("User pinned a message")
        elif message.pinned_message and s.get("del_pins", False):
            await message.delete()
            
        # 5. Group Info Changes (New Photo, Deleted Photo, New Title)
        elif (message.new_chat_photo or message.delete_chat_photo or message.new_chat_title) and s.get("del_info", False):
            await message.delete()
            
    except Exception as e:
        # Fails silently if the bot doesn't have "Delete Messages" admin rights
        pass
