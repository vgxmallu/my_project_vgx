import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from pyrogram.enums import ChatMemberStatus
from vgx.database.welcm_db import get_group_greetings, update_group_greetings

# --- Security Check ---
async def is_admin(client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except:
        return False

# --- UI Builder ---
def build_greetings_menu(chat_id: int, s: dict):
    welc_btn = "🟢 Welcome: ON" if s.get("welcome_enabled") else "🔴 Welcome: OFF"
    leave_btn = "🟢 Leave: ON" if s.get("leave_enabled") else "🔴 Leave: OFF"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(welc_btn, callback_data=f"grt_tgl_welc_{chat_id}"),
         InlineKeyboardButton(leave_btn, callback_data=f"grt_tgl_leave_{chat_id}")],
        [InlineKeyboardButton("📝 Set Welcome Msg", callback_data=f"grt_set_welc_{chat_id}")],
        [InlineKeyboardButton("📝 Set Leave Msg", callback_data=f"grt_set_leave_{chat_id}")]
    ])

async def refresh_menu(query, chat_id: int):
    s = await get_group_greetings(chat_id)
    inv_stamp = f" \u200b" * int(time.time() % 3)
    
    # ✅ Safely fetch the texts, providing a fallback if they are missing
    welc_msg = s.get("welcome_text", "Hey {{first_name}}❤️, welcome to {{group}} 🥳")
    leave_msg = s.get("leave_text", "Goodbye {{first_name}}, we will miss you! 😢")
    
    text = (
        "⚙️ **Greetings Control Panel**\n"
        f"🎯 **Target:** `{chat_id}`{inv_stamp}\n\n"
        f"**Welcome Msg:**\n`{welc_msg}`\n\n"
        f"**Leave Msg:**\n`{leave_msg}`"
    )
    try:
        await query.message.edit_text(text, reply_markup=build_greetings_menu(chat_id, s))
    except Exception:
        pass


@Client.on_message(filters.command("greetings") & filters.group)
async def greetings_cmd(client, message):
    chat_id = message.chat.id
    if not await is_admin(client, chat_id, message.from_user.id):
        return await message.reply("❌ Only admins can configure greetings.")
        
    s = await get_group_greetings(chat_id)
    
    # ✅ Safely fetch the texts here too!
    welc_msg = s.get("welcome_text", "Hey {{first_name}}❤️, welcome to {{group}} 🥳")
    leave_msg = s.get("leave_text", "Goodbye {{first_name}}, we will miss you! 😢")
    
    text = (
        "⚙️ **Greetings Control Panel**\n"
        f"🎯 **Target:** `{chat_id}`\n\n"
        f"**Welcome Msg:**\n`{welc_msg}`\n\n"
        f"**Leave Msg:**\n`{leave_msg}`"
    )
    await message.reply(text, reply_markup=build_greetings_menu(chat_id, s))
    
# --- Callbacks ---
@Client.on_callback_query(filters.regex(r"^grt_(?P<action>tgl|set)_(?P<type>welc|leave)_(?P<chat_id>-?\d+)$"))
async def greetings_callbacks(client, query):
    action = query.matches[0].group("action")
    msg_type = query.matches[0].group("type")
    chat_id = int(query.matches[0].group("chat_id"))
    
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("❌ Admin strictly required.", show_alert=True)
        
    s = await get_group_greetings(chat_id)
    
    if action == "tgl":
        if msg_type == "welc":
            await update_group_greetings(chat_id, welcome_enabled=not s.get("welcome_enabled"))
        elif msg_type == "leave":
            await update_group_greetings(chat_id, leave_enabled=not s.get("leave_enabled"))
        await refresh_menu(query, chat_id)
        
    elif action == "set":
        msg_name = "Welcome" if msg_type == "welc" else "Leave"
        await query.message.reply(
            f"✏️ **Editing {msg_name} Message for {chat_id}**\n\n"
            "Send me the new message now! You can use Markdown and these placeholders:\n"
            "`{{first_name}}`, `{{last_name}}`, `{{name}}`, `{{group}}`, `{{count}}`",
            reply_markup=ForceReply(selective=True)
        )
        await query.answer()

# --- Handle Forced Replies (Saving Custom Texts) ---
@Client.on_message(filters.reply & filters.group)
async def handle_custom_text(client, message):
    if not message.reply_to_message or not message.reply_to_message.text:
        return
        
    original_text = message.reply_to_message.text
    
    if "Editing Welcome Message for" in original_text:
        if not await is_admin(client, message.chat.id, message.from_user.id): return
        chat_id = int(original_text.split("for ")[1].split("\n")[0])
        await update_group_greetings(chat_id, welcome_text=message.text.markdown)
        await message.reply("✅ **Custom Welcome Message saved successfully!**")
        
    elif "Editing Leave Message for" in original_text:
        if not await is_admin(client, message.chat.id, message.from_user.id): return
        chat_id = int(original_text.split("for ")[1].split("\n")[0])
        await update_group_greetings(chat_id, leave_text=message.text.markdown)
        await message.reply("✅ **Custom Leave Message saved successfully!**")
