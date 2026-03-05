import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.welcm_db import get_group_greetings

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
