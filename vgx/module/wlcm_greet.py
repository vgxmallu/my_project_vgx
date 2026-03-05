from pyrogram import Client, filters
from vgx.database.welcm_db import get_group_greetings

def format_greeting(template: str, user, chat, member_count: int) -> str:
    """Safely replaces placeholders with real data."""
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip() or "Member"
    
    return template.replace("{{first_name}}", first_name) \
                   .replace("{{last_name}}", last_name) \
                   .replace("{{name}}", full_name) \
                   .replace("{{group}}", chat.title or "") \
                   .replace("{{count}}", str(member_count))

@Client.on_message(filters.new_chat_members)
async def welcome_new_members(client, message):
    chat_id = message.chat.id
    s = await get_group_greetings(chat_id)
    
    if not s.get("welcome_enabled"):
        return # Do nothing if module is off
        
    # Get total member count for the {{count}} placeholder
    count = await client.get_chat_members_count(chat_id)
    
    for new_member in message.new_chat_members:
        # Prevent the bot from greeting itself if it's newly added
        if new_member.is_self:
            continue
            
        text = format_greeting(s["welcome_text"], new_member, message.chat, count)
        await message.reply(text, disable_web_page_preview=True)

@Client.on_message(filters.left_chat_member)
async def say_goodbye(client, message):
    chat_id = message.chat.id
    s = await get_group_greetings(chat_id)
    
    if not s.get("leave_enabled"):
        return
        
    left_member = message.left_chat_member
    if left_member.is_self:
        return
        
    count = await client.get_chat_members_count(chat_id)
    text = format_greeting(s["leave_text"], left_member, message.chat, count)
    
    await message.reply(text, disable_web_page_preview=True)
