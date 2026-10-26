from pyrogram import Client, filters, enums
from vgx import app
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import asyncio
from pyrogram.enums import ButtonStyle
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
        InlineKeyboardButton("❌ Close Help", callback_data="close", style=ButtonStyle.DANGER),
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
            InlineKeyboardButton("🚀 Quick Start", callback_data="help_quick", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("📋 Commands", callback_data="help_cmds", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("⚙️ Job Settings", callback_data="help_settings", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("🛠️ Managing Jobs", callback_data="help_manage", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("❌", callback_data="close", style=ButtonStyle.DANGER),
            InlineKeyboardButton("⬅️", callback_data="help_menu")
    ]]
)
    if data == "help_menu":
        text = (
            "Select your catagory:\n/start me again?"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Group Menu", callback_data="help_gp", style=ButtonStyle.PRIMARY)
            ],[
                InlineKeyboardButton("Scheduler Menu", callback_data="help_home", style=ButtonStyle.PRIMARY)
            ],[
                InlineKeyboardButton("RSS Menu", callback_data="rss_home", style=ButtonStyle.PRIMARY)
            [
                InlineKeyboardButton("❌", callback_data="close", style=ButtonStyle.DANGER)
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



# ==================================================================
# 6. HELP MENU & INTERACTIVE GUIDE (/rsshelp)
# ==================================================================

@Client.on_callback_query(filters.regex(r"^rss_(?P<section>[a-z]+)$"))
async def rss_help_callbacks(client, query):
    section = query.matches[0].group("section")
    
    keyboard_back = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Help Menu", callback_data="rss_help_home", style=ButtonStyle.PRIMARY)]
    ])
    
    if section == "home":
        text = (
            "📡 **RSS Feed Manager - Help Center**\n\n"
            "Welcome! This bot automatically fetches RSS/ATOM feeds and posts updates to your Telegram chats or channels.\n\n"
            "👇 **Select a category below to learn more:**"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚀 Quick Start", callback_data="rss_quick", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("📋 Commands", callback_data="rss_cmds", style=ButtonStyle.PRIMARY)
            ],
            [
                InlineKeyboardButton("⚙️ Settings Guide", callback_data="rss_settings", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("✏️ Custom Templates", callback_data="rss_templates", style=ButtonStyle.PRIMARY)
            ],
            [
                InlineKeyboardButton("❌ Close Help", callback_data="cancel", style=ButtonStyle.DANGER)
            ]
        ])
        await query.message.edit_text(text, reply_markup=keyboard)
        
    elif section == "quick":
        text = (
            "🚀 **Quick Start Guide**\n\n"
            "1. Make sure you are chatting with the bot in **Private Chat**.\n"
            "2. Run `/addfeed <chat_id>` (e.g., `/addfeed -100123456789`) for your target group or channel.\n"
            "3. **Reply** to the bot's prompt with your valid RSS or ATOM feed URL(s).\n"
            "4. Manage and customize your feeds anytime using `/managerss <chat_id>`!"
        )
        await query.message.edit_text(text, reply_markup=keyboard_back)
        
    elif section == "cmds":
        text = (
            "📋 **Commands Reference**\n\n"
            "• `/rss` — View basic bot introduction.\n"
            "• `/addfeed <chat_id>` — Connect new RSS/ATOM feed URLs (max 5 per chat).\n"
            "• `/managerss` (or `/manage`) `<chat_id>` — Open the interactive configuration panel for a chat's feeds.\n"
            "• `/rsshelp` — Open this interactive help center."
        )
        await query.message.edit_text(text, reply_markup=keyboard_back)
        
    elif section == "settings":
        text = (
            "⚙️ **Feed Settings & Panel Explained**\n\n"
            "• 🟢/🔴 **Enabled:** Toggle whether the feed is active or paused.\n"
            "• 📝 **Format:** Switch between Markdown and HTML formatting for posts.\n"
            "• 🖼 **Images:** Enable or disable sending images extracted from feed items.\n"
            "• 🔗 **Preview:** Turn Telegram web link previews ON or OFF.\n"
            "• 🔕 **Notify:** Toggle silent notifications for incoming updates.\n"
            "• 🔄 **Clear Cache:** Reset the posted history cache so old posts re-send on the next fetch cycle.\n"
            "• 🗑 **Delete Source:** Permanently remove the feed configuration."
        )
        await query.message.edit_text(text, reply_markup=keyboard_back)
        
    elif section == "templates":
        text = (
            "✏️ **Custom Templates Guide**\n\n"
            "You can customize how your feed updates are formatted by clicking **✏️ Edit Template** on any feed configuration panel.\n\n"
            "• **How to use:** Click the button, then reply to the prompt with your custom text pattern.\n"
            "• **Common Placeholders:** `{{title}}`, `{{link}}`, `{{summary}}`, `{{author}}`"
        )
        await query.message.edit_text(text, reply_markup=keyboard_back)
        
    await query.answer()
