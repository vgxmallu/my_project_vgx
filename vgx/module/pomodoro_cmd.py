

"""
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==========================================
# 1. Pomodoro Help Text Dictionary
# ==========================================
POMO_HELP_TEXT = {
    "home": (
        "🍅 **Pomodoro Sprint Manager**\n\n"
        "Welcome to the productivity module! This feature allows admins to temporarily lock a group chat so members can focus on studying or working without distractions.\n\n"
        "👇 **Choose a category to learn how it works:**"
    ),
    "setup": (
        "⚙️ **How to Setup (Bot Owner/Admin)**\n\n"
        "Before a group can use the sprint feature, it must be enabled in the bot's private messages.\n\n"
        "🔹 **Command:** `/pomotarget <group_id>`\n"
        "🔹 **Example:** `/pomotarget -100123456789`\n\n"
        "Send this to me in a private message. A menu will appear allowing you to **Enable** or **Disable** the Pomodoro module for that specific group."
    ),
    "usage": (
        "🚀 **How to Start a Sprint (In Group)**\n\n"
        "Once enabled, group admins can start a focus sprint. The bot will lock the chat, and automatically unlock it when the timer ends.\n\n"
        "🔹 **Command:** `/sprint <minutes>` or `/focus <minutes>`\n"
        "🔹 **Example:** `/sprint 25m`\n\n"
        "⚠️ *Note: Sprints must be between 1 and 120 minutes. The bot requires the 'Ban Users' admin permission to restrict chat permissions.*"
    )
}

# ==========================================
# 2. Keyboards (Buttons)
# ==========================================
def get_pomo_home_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚙️ Setup Guide", callback_data="pomohelp_setup"),
            InlineKeyboardButton("🚀 Usage", callback_data="pomohelp_usage")
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="pomohelp_close")
        ]
    ])

def get_pomo_back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Pomodoro Menu", callback_data="pomohelp_home")]
    ])

# ==========================================
# 3. The /pomohelp Command Trigger
# ==========================================
@Client.on_message(filters.command("pomohelp"))
async def send_pomo_help(client, message):
    await message.reply_text(
        text=POMO_HELP_TEXT["home"],
        reply_markup=get_pomo_home_keyboard()
    )

# ==========================================
# 4. The Regex Callback Handler
# ==========================================
@Client.on_callback_query(filters.regex(r"^pomohelp_(?P<category>[a-z_]+)$"))
async def pomo_help_clicks(client, query):
    category = query.matches[0].group("category")

    # 1. Handle Close
    if category == "close":
        await query.message.delete()
        return

    # 2. Handle Home / Back
    if category == "home":
        text = POMO_HELP_TEXT["home"]
        keyboard = get_pomo_home_keyboard()
        
    # 3. Handle Category Pages (setup, usage)
    elif category in POMO_HELP_TEXT:
        text = POMO_HELP_TEXT[category]
        keyboard = get_pomo_back_keyboard()
        
    else:
        return await query.answer("Page not found!", show_alert=True)

    # 4. Edit the message smoothly
    try:
        await query.message.edit_text(
            text=text,
            reply_markup=keyboard
        )
        await query.answer()
    except Exception:
        await query.answer()
"""


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
