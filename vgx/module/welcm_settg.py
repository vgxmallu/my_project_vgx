import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from pyrogram.enums import ChatMemberStatus
from vgx.database.welcm_db import get_group_greetings, update_group_greetings
from pyrogram.enums import ButtonStyle
import re

"""
👋 **Greetings & Welcome Module Guide**

Make your group feel like home! I can greet new members and say goodbye to leaving members using fully customizable messages, media, and inline buttons.

🛠 **How to Setup:**
1. Add me to your group and promote me to **Admin**.
2. Type `/greetings` in the group to open the Control Panel.
3. Click **"Set Welcome Msg"** or **"Set Leave Msg"**.
4. Reply to my prompt with your custom message!

🖼 **Adding Media:**
Want to send a Photo, GIF, or Video? Simply upload the media and type your welcome text into the **Caption** before sending!

✨ **Dynamic Placeholders:**
Use these tags in your text, and I will automatically replace them with the real info:
• `{{first_name}}` - The user's first name
• `{{last_name}}` - The user's last name
• `{{name}}` - The user's full name
• `{{group}}` - The name of your group
• `{{count}}` - The total number of members

🔗 **Adding Inline Buttons:**
You can add beautiful clickable buttons to the bottom of your message! Just type them anywhere in your text using this exact format:
`[Button Text | https://your-link.com]`

**Example Message:**
Hey {{first_name}}! Welcome to {{group}} 🥳
You are our {{count}}th member! Please read the rules below.
[Read Rules | https://t.me/your_rules_link]

⚠️ *Note: Only Group Admins can use the `/greetings` command.*

"""

# --- Security Check & UI Builders remain the same ---
async def is_admin(client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except:
        return False

def build_greetings_menu(chat_id: int, s: dict):
    welc_btn = "🟢 Welcome: ON" if s.get("welcome_enabled") else "🔴 Welcome: OFF"
    leave_btn = "🟢 Leave: ON" if s.get("leave_enabled") else "🔴 Leave: OFF"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(welc_btn, callback_data=f"grt_tgl_welc_{chat_id}", style=ButtonStyle.PRIMARY),
         InlineKeyboardButton(leave_btn, callback_data=f"grt_tgl_leave_{chat_id}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("📝 Set Welcome Msg", callback_data=f"grt_set_welc_{chat_id}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("📝 Set Leave Msg", callback_data=f"grt_set_leave_{chat_id}", style=ButtonStyle.PRIMARY)]
    ])

async def refresh_menu(query, chat_id: int):
    s = await get_group_greetings(chat_id)
    inv_stamp = f" \u200b" * int(time.time() % 3)
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
    welc_msg = s.get("welcome_text", "Hey {{first_name}}❤️, welcome to {{group}} 🥳")
    leave_msg = s.get("leave_text", "Goodbye {{first_name}}, we will miss you! 😢")
    
    text = (
        "⚙️ **Greetings Control Panel**\n"
        f"🎯 **Target:** `{chat_id}`\n\n"
        f"**Welcome Msg:**\n`{welc_msg}`\n\n"
        f"**Leave Msg:**\n`{leave_msg}`"
    )
    await message.reply(text, reply_markup=build_greetings_menu(chat_id, s))

@Client.on_callback_query(filters.regex(r"^grt_(?P<action>tgl|set)_(?P<type>welc|leave)_(?P<chat_id>-?\d+)$"))
async def greetings_callbacks(client, query):
    action = query.matches[0].group("action")
    msg_type = query.matches[0].group("type")
    chat_id = int(query.matches[0].group("chat_id"))
    
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("❌ Admin strictly required.", show_alert=True)
        
    s = await get_group_greetings(chat_id)
    
    if action == "tgl":
        if msg_type == "welc": await update_group_greetings(chat_id, welcome_enabled=not s.get("welcome_enabled"))
        elif msg_type == "leave": await update_group_greetings(chat_id, leave_enabled=not s.get("leave_enabled"))
        await refresh_menu(query, chat_id)
        
    elif action == "set":
        msg_name = "Welcome" if msg_type == "welc" else "Leave"
        await query.message.reply(
            f"✏️ **Editing {msg_name} Message for {chat_id}**\n\n"
            "Send me your new message (Text, Photo, GIF, or Video).\n"
            "**Placeholders:** `{{first_name}}`, `{{last_name}}`, `{{name}}`, `{{group}}`, `{{count}}`\n"
            "**Buttons:** `[Button Name | https://link.com]`",
            reply_markup=ForceReply(selective=True)
        )
        await query.answer()

# ✅ THE UPGRADED MEDIA HANDLER
@Client.on_message(filters.reply & filters.group)
async def handle_custom_text(client, message):
    if not message.reply_to_message or not message.reply_to_message.text: return
    original_text = message.reply_to_message.text
    
    if "Editing Welcome Message for" in original_text or "Editing Leave Message for" in original_text:
        chat_id = int(original_text.split("for ")[1].split("\n")[0])
        if not await is_admin(client, chat_id, message.from_user.id): return
        
        # 1. Detect Media and Text Content safely
        media_id = None
        media_type = None
        text_content = ""

        if message.animation:
            media_id = message.animation.file_id
            media_type = "animation"
            text_content = message.caption.markdown if message.caption else ""
        elif message.video:
            media_id = message.video.file_id
            media_type = "video"
            text_content = message.caption.markdown if message.caption else ""
        elif message.photo:
            media_id = message.photo.file_id
            media_type = "photo"
            text_content = message.caption.markdown if message.caption else ""
        elif message.text:
            text_content = message.text.markdown

        # 2. Save to Database based on which message we are editing
        if "Welcome" in original_text:
            await update_group_greetings(chat_id, welcome_text=text_content, welcome_media_id=media_id, welcome_media_type=media_type)
            await message.reply("✅ **Media & Custom Welcome Message saved!**")
        else:
            await update_group_greetings(chat_id, leave_text=text_content, leave_media_id=media_id, leave_media_type=media_type)
            await message.reply("✅ **Media & Custom Leave Message saved!**")


def parse_buttons_and_format(template: str, user, chat, member_count: int):
    """Replaces placeholders AND extracts inline buttons from the text."""
    
    # 1. Replace Standard Placeholders
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip() or "Member"
    
    formatted_text = template.replace("{{first_name}}", first_name) \
                             .replace("{{last_name}}", last_name) \
                             .replace("{{name}}", full_name) \
                             .replace("{{group}}", chat.title or "") \
                             .replace("{{count}}", str(member_count))

    # 2. Extract Custom Buttons using Regex [Button Name | https://link.com]
    buttons = []
    pattern = r"\[([^\|\]]+)\|\s*(https?://[^\s\]]+)\]"
    
    matches = re.findall(pattern, formatted_text)
    for match in matches:
        btn_text = match[0].strip()
        btn_url = match[1].strip()
        # Add each button to a new row. (You can modify this to group them if you want)
        buttons.append([InlineKeyboardButton(btn_text, url=btn_url)])
        
    # 3. Strip the button syntax out of the final message text
    clean_text = re.sub(pattern, "", formatted_text).strip()
    
    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
    
    return clean_text, reply_markup

# --- Dispatcher Engine ---
async def send_greeting(client, chat_id, text_template, media_id, media_type, user, chat, count):
    """Handles sending the correct format (Text, Photo, Video, GIF)."""
    clean_text, keyboard = parse_buttons_and_format(text_template, user, chat, count)
    
    try:
        if media_type == "photo":
            await client.send_photo(chat_id, photo=media_id, caption=clean_text, reply_markup=keyboard)
        elif media_type == "video":
            await client.send_video(chat_id, video=media_id, caption=clean_text, reply_markup=keyboard)
        elif media_type == "animation":
            await client.send_animation(chat_id, animation=media_id, caption=clean_text, reply_markup=keyboard)
        else:
            await client.send_message(chat_id, text=clean_text, reply_markup=keyboard, disable_web_page_preview=True)
    except Exception as e:
        print(f"Failed to send greeting to {chat_id}: {e}")

@Client.on_message(filters.new_chat_members)
async def welcome_new_members(client, message):
    chat_id = message.chat.id
    s = await get_group_greetings(chat_id)
    
    if not s.get("welcome_enabled"): return
        
    count = await client.get_chat_members_count(chat_id)
    
    for new_member in message.new_chat_members:
        if new_member.is_self: continue
            
        await send_greeting(
            client, chat_id, 
            s.get("welcome_text", ""), 
            s.get("welcome_media_id"), 
            s.get("welcome_media_type"), 
            new_member, message.chat, count
        )

@Client.on_message(filters.left_chat_member)
async def say_goodbye(client, message):
    chat_id = message.chat.id
    s = await get_group_greetings(chat_id)
    
    if not s.get("leave_enabled"): return
        
    left_member = message.left_chat_member
    if left_member.is_self: return
        
    count = await client.get_chat_members_count(chat_id)
    await send_greeting(
        client, chat_id, 
        s.get("leave_text", ""), 
        s.get("leave_media_id"), 
        s.get("leave_media_type"), 
        left_member, message.chat, count
    )
