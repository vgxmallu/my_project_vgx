from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from vgx.database.channel_db import get_user, get_channel, update_channel, channels_col

def build_dashboard_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ Create Post", callback_data="chm_create_post"),
         InlineKeyboardButton("📚 Multipost", callback_data="chm_multipost")],
        [InlineKeyboardButton("⚙️ Channel Settings", callback_data="chm_select_channel")],
        [InlineKeyboardButton("🪧 Service Messages", callback_data="chm_service_msgs"),
         InlineKeyboardButton("📋 Auto-complete", callback_data="chm_autocomplete")],
        [InlineKeyboardButton("🏃‍♂️ Welcome/Goodbye", callback_data="chm_welcome_goodbye")],
        [InlineKeyboardButton("🌎 Time Zone", callback_data="chm_set_timezone"),
         InlineKeyboardButton("📤 Forward (PLUS ⭐️)", callback_data="chm_forwarding")]
    ])

@Client.on_message(filters.command("channel") & filters.private)
async def start_cjhmd(client, message):
    user = await get_user(message.from_user.id)
    tz = user.get("timezone", "UTC")
    
    text = (
        "👋 **Welcome to the Advanced Channel Manager!**\n\n"
        "Manage your channels, schedule posts with rich media and inline buttons, "
        "and track user reactions all in one place.\n\n"
        f"🌍 **Your Timezone:** `{tz}`\n"
        "👇 *Select an option below to get started:*"
    )
    await message.reply(text, reply_markup=build_dashboard_menu())

@Client.on_callback_query(filters.regex(r"^chm_main_menu$"))
async def back_to_main(client, query):
    await query.message.edit_text("👇 *Main Menu*", reply_markup=build_dashboard_menu())



def build_channel_settings_menu(chat_id: int, s: dict):
    svc_btn = "🟢 Service Msgs: ON" if s.get("del_service_msgs") else "🔴 Service Msgs: OFF"
    ban_btn = "🟢 Leave Ban: ON" if s.get("leave_ban_time", 0) > 0 else "🔴 Leave Ban: OFF"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✒️ Edit Signature", callback_data=f"chm_set_sig_{chat_id}"),
         InlineKeyboardButton("👍👎 Default Reactions", callback_data=f"chm_set_reac_{chat_id}")],
        [InlineKeyboardButton(svc_btn, callback_data=f"chm_tgl_svc_{chat_id}"),
         InlineKeyboardButton(ban_btn, callback_data=f"chm_tgl_ban_{chat_id}")],
        [InlineKeyboardButton("🔙 Back to Dashboard", callback_data="chm_main_menu")]
    ])

@Client.on_callback_query(filters.regex(r"^chm_select_channel$"))
async def select_channel_menu(client, query):
    # Fetch channels owned by this user from DB
    cursor = channels_col.find({"owner_id": query.from_user.id})
    channels = await cursor.to_list(length=None)
    
    if not channels:
        return await query.answer("⚠️ Add me to a channel as Admin first!", show_alert=True)
        
    buttons = [[InlineKeyboardButton(ch.get("title", str(ch["chat_id"])), callback_data=f"chm_cfg_{ch['chat_id']}")] for ch in channels]
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="chm_main_menu")])
    
    await query.message.edit_text("⚙️ **Select a channel to configure:**", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^chm_cfg_(?P<chat_id>-?\d+)$"))
async def channel_config(client, query):
    chat_id = int(query.matches[0].group("chat_id"))
    s = await get_channel(chat_id)
    
    reacs = " ".join(s.get('default_reactions', [])) or "None"
    sig = s.get('signature', 'None')
    
    text = (
        f"⚙️ **Settings for** `{chat_id}`\n\n"
        f"**Signature:**\n`{sig}`\n\n"
        f"**Default Reactions:** {reacs}"
    )
    await query.message.edit_text(text, reply_markup=build_channel_settings_menu(chat_id, s))

# --- Handle Toggles & Edits ---
@Client.on_callback_query(filters.regex(r"^chm_(?P<action>tgl|set)_(?P<param>[a-z_]+)_(?P<chat_id>-?\d+)$"))
async def settings_callbacks(client, query):
    action = query.matches[0].group("action")
    param = query.matches[0].group("param")
    chat_id = int(query.matches[0].group("chat_id"))
    
    s = await get_channel(chat_id)
    
    if action == "tgl":
        if param == "svc": await update_channel(chat_id, del_service_msgs=not s.get("del_service_msgs"))
        # Refresh the config menu (You would call channel_config logic here)
        await query.answer("Setting Updated!")
        
    elif action == "set":
        if param == "sig":
            await query.message.reply(
                f"✒️ **Editing Signature for {chat_id}**\nReply with your new signature (Supports HTML/Markdown).",
                reply_markup=ForceReply(selective=True)
            )
        elif param == "reac":
            await query.message.reply(
                f"👍 **Editing Default Reactions for {chat_id}**\nReply with emojis separated by spaces (e.g., `👍 ❤️ 😂`).",
                reply_markup=ForceReply(selective=True)
            )
        await query.answer()


@Client.on_chat_join_request()
async def handle_join_request(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    s = await get_channel(chat_id)
    # If the channel uses the Welcome feature
    if s.get("welcome_enabled"):
        await client.approve_chat_join_request(chat_id, user_id)
        # Send Welcome Message to user privately
        try:
            await client.send_message(user_id, f"Welcome to {message.chat.title}!")
        except:
            pass # User hasn't started the bot

@Client.on_message(filters.left_chat_member)
async def handle_leave(client, message):
    chat_id = message.chat.id
    s = await get_channel(chat_id)
    
    # 🏃‍♂️ Goodbye Ban Logic
    ban_time = s.get("leave_ban_time", 0)
    if ban_time > 0:
        # Banning logic goes here using client.ban_chat_member
        pass
