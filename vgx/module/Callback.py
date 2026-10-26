from pyrogram import Client, filters, enums
from vgx import app
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import asyncio

# ==================================================================
# 1. HELP COMMAND HANDLER (/help)
# ==================================================================

keyboard = InlineKeyboardMarkup(
    [[
        InlineKeyboardButton("🚀 Quick Start", callback_data="help_quick"),
        InlineKeyboardButton("📋 Commands", callback_data="help_cmds")
    ],
    [
        InlineKeyboardButton("⚙️ Job Settings", callback_data="help_settings"),
        InlineKeyboardButton("🛠️ Managing Jobs", callback_data="help_manage")
    ],
    [
        InlineKeyboardButton("❌ Close Help", callback_data="close"),
        InlineKeyboardButton("⬅️", callback_data="help_menu")
    ]]
)

@Client.on_message(filters.private & filters.command("help"))
async def help_command(c, m):
    help_text = (
        "🤖 **Bot Scheduler - Master Help Menu**\n\n"
        "Welcome! This bot allows you to automate recurring messages, "
        "manage posts, and configure advanced delivery options.\n\n"
        "👇 **Select a category below to learn more:**"
    )
    
    await m.reply(help_text, reply_markup=keyboard)


# ==================================================================
# 2. HELP CALLBACK NAVIGATION HANDLERS
# ==================================================================


@Client.on_callback_query(filters.regex(r"^help_"))
async def help_navigation_callbacks(c, q):
    data = q.data
    keyboard_back = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Help Menu", callback_data="help_home")]
    ])
    
    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("🚀 Quick Start", callback_data="help_quick"),
            InlineKeyboardButton("📋 Commands", callback_data="help_cmds")
        ],
        [
            InlineKeyboardButton("⚙️ Job Settings", callback_data="help_settings"),
            InlineKeyboardButton("🛠️ Managing Jobs", callback_data="help_manage")
        ],
        [
            InlineKeyboardButton("❌", callback_data="close"),
            InlineKeyboardButton("⬅️", callback_data="help_menu")
    ]]
)
    if data == "help_menu":
        text = (
            "Select your catagory:\n/start me again?"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Group Menu", callback_data="help_gp"),
                InlineKeyboardButton("Scheduler Menu", callback_data="help_home")
            ],
            [
                InlineKeyboardButton("❌", callback_data="close")
            ]
        ])
        await q.message.edit_text(text, reply_markup=keyboard)
        
    elif data == "help_home":
        text = (
            "🤖 **Bot Scheduler - Master Help Menu**\n\n"
            "Welcome! This bot allows you to automate recurring messages, "
            "manage posts, and configure advanced delivery options.\n\n"
            "👇 **Select a category below to learn more:**"
        )
        await q.message.edit_text(text, reply_markup=keyboard)

    elif data == "help_quick":
        text = (
            "🚀 **Quick Start Guide**\n\n"
            "1. Type `/schedule` in private chat to open the wizard dashboard.\n"
            "2. Click **Target** and use `/settarget <chat_id>` to define where messages go.\n"
            "3. Click **Content**, then **reply** to any message/media with `/settext` or `/setcontent`.\n"
            "4. Configure intervals and preferences, then click **Save & Start**!"
        )
        await q.message.edit_text(text, reply_markup=keyboard_back)
        
  
    elif data == "help_cmds":
        text = (
            "📋 **Available Commands Reference**\n\n"
            "• `/schedule` — Opens the creation wizard.\n"
            "• `/myjobs` — Lists all your active and paused jobs.\n"
            "• `/settext` or `/setcontent` — **(Must reply to a message)** Saves text, photos, videos, or stickers into your active session.\n"
            "• `/settarget <chat_id>` — Sets the target destination channel/chat ID.\n"
            "• `/help` — Opens this help menu."
        )
        await q.message.edit_text(text, reply_markup=keyboard_back)
        
    elif data == "help_settings":
        text = (
            "⚙️ **Job Settings & Options**\n\n"
            "• **Interval:** Choose how often your message repeats (e.g., 5m, 10m, 30m, 60m). Set to 0 for one-time sending.\n"
            "• **Pin Message:** Automatically pins the sent message in the target chat.\n"
            "• **Delete Last Message:** Cleans up the previous bot post before sending a new one.\n"
            "• **Auto-Delete:** Sets a timer for the message to self-destruct after delivery (e.g., 30s, 5m, 1h)."
        )
        await q.message.edit_text(text, reply_markup=keyboard_back)
        
    elif data == "help_manage":
        text = (
            "🛠️ **Managing Existing Jobs**\n\n"
            "• Run `/myjobs` to view all your scheduled tasks.\n"
            "• Click any job item to open its control panel.\n"
            "• **Pause / Resume:** Temporarily halt or restart the schedule.\n"
            "• **Edit Content:** Swap out the media or text of a running job instantly.\n"
            "• **Delete:** Permanently cancel and delete the job."
        )
        await q.message.edit_text(text, reply_markup=keyboard_back)
        
    await q.answer()
