import re
from pyrogram import Client, filters
from pyrogram.types import ChatPermissions
from pyrogram.enums import ChatMemberStatus
from vgx.database.pomodoro_db import get_pomo_settings, start_sprint_db

async def is_admin(client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except:
        return False

@Client.on_message(filters.command(["sprint", "focus"]) & filters.group)
async def start_sprint(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # 1. Check if module is enabled for this group
    s = await get_pomo_settings(chat_id)
    if not s["enabled"]:
        return # Do nothing if disabled
        
    # 2. Security Check
    if not await is_admin(client, chat_id, user_id):
        return await message.reply("❌ Only admins can start a productivity sprint.")

    # 3. Parse the time (e.g., /sprint 25 or /sprint 25m)
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/sprint 25m`")
        
    time_str = message.command[1]
    match = re.search(r"(\d+)", time_str)
    if not match:
        return await message.reply("❌ Please provide a valid number of minutes.")
        
    minutes = int(match.group(1))
    if minutes < 1 or minutes > 120:
        return await message.reply("⚠️ Sprints must be between 1 and 120 minutes.")

    # 4. Lock the Chat
    try:
        # Disable sending messages
        await client.set_chat_permissions(
            chat_id, 
            ChatPermissions(can_send_messages=False)
        )
    except Exception as e:
        return await message.reply("❌ I lack the 'Ban Users' admin rights needed to lock the chat.")

    # 5. Save to Database
    await start_sprint_db(chat_id, minutes)
    
    # 6. Announce
    await message.reply(f"🤫 **Focus mode activated!**\nGroup locked for **{minutes} minutes**.\nTime to work/study! 🍅")
