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
        InlineKeyboardButton("🚀 Quick Start", callback_data="help_quick", style=ButtonStyle.PRIMARY),
        InlineKeyboardButton("📋 Commands", callback_data="help_cmds", style=ButtonStyle.PRIMARY)
    ],
    [
        InlineKeyboardButton("⚙️ Job Settings", callback_data="help_settings", style=ButtonStyle.PRIMARY),
        InlineKeyboardButton("🛠️ Managing Jobs", callback_data="help_manage", style=ButtonStyle.PRIMARY)
    ],
    [
        InlineKeyboardButton("❌", callback_data="close", style=ButtonStyle.DANGER),
        InlineKeyboardButton("🔙", callback_data="help_menu", style=ButtonStyle.PRIMARY)
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

@app.on_callback_query(filters.regex("^close$"))
async def colce_callback(client, query):
    await query.answer("Closed ❌")
    await asyncio.sleep(2)
    await query.message.delete()
    
    
@Client.on_callback_query(filters.regex(r"^help_"))
async def help_navigation_callbacks(c, q):
    data = q.data
    keyboard_back = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Help Menu", callback_data="help_home", style=ButtonStyle.PRIMARY)]
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
            InlineKeyboardButton("🔙", callback_data="help_menu", style=ButtonStyle.PRIMARY)
    ]]
)
    if data == "help_menu":
        text = (
            "Select your catagory:\n/start me again?"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Group Menu", callback_data="help_gp", style=ButtonStyle.SUCCESS)
            ],[
                InlineKeyboardButton("📨 Scheduler Menu", callback_data="help_home", style=ButtonStyle.SUCCESS)
            ],[
                InlineKeyboardButton("📢 RSS Menu", callback_data="rss_home", style=ButtonStyle.SUCCESS)
            ],[
                InlineKeyboardButton("🧝🏻‍♀️ Anime Menu", callback_data="anime_home", style=ButtonStyle.SUCCESS)
            ],[
                InlineKeyboardButton("📊 Analytics Menu", callback_data="anlyz_home", style=ButtonStyle.SUCCESS)
            ],[
                InlineKeyboardButton("⚽ Football Menu", callback_data="fob_home", style=ButtonStyle.SUCCESS)
            ],[
                InlineKeyboardButton("💜 Deezer Menu", callback_data="deez_home", style=ButtonStyle.SUCCESS)
            ],[
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
            "2. Click **Target** and use `/settarget chat_id` to define where messages go.\n"
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
            "• `/settarget chat_id` — Sets the target destination channel/chat ID.\n"
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
        [InlineKeyboardButton("🔙 Back to Help Menu", callback_data="rss_home", style=ButtonStyle.PRIMARY)]
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
                InlineKeyboardButton("❌", callback_data="close", style=ButtonStyle.DANGER),
                InlineKeyboardButton("🔙", callback_data="help_menu", style=ButtonStyle.PRIMARY)
            ]
        ])
        await query.message.edit_text(text, reply_markup=keyboard)
        
    elif section == "quick":
        text = (
            "🚀 **Quick Start Guide**\n\n"
            "1. Make sure you are chatting with the bot in **Private Chat**.\n"
            "2. Run `/addfeed chat_id` (e.g., `/addfeed -100123456789`) for your target group or channel.\n"
            "3. **Reply** to the bot's prompt with your valid RSS or ATOM feed URL(s).\n"
            "4. Manage and customize your feeds anytime using `/managerss <chat_id>`!"
        )
        await query.message.edit_text(text, reply_markup=keyboard_back)
        
    elif section == "cmds":
        text = (
            "📋 **Commands Reference**\n\n"
            "• `/rss` — View basic bot introduction.\n"
            "• `/addfeed chat_id` — Connect new RSS/ATOM feed URLs (max 5 per chat).\n"
            "• `/managerss` (or `/manage`) `chat_id` — Open the interactive configuration panel for a chat's feeds.\n"
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
            "• **Common Placeholders:** `{{title}}`, `{{link}}`, `{{summary}}`, `{{author}}`, `{{content}}`, `{{shortlink}}`, `{{tags}}`, Date: `{{y}} - {{d}} - {{m}}`, Time: `{{t}}`, `{{channel_title}}`, `{{feed_title}}`"
        )
        await query.message.edit_text(text, reply_markup=keyboard_back)
        
    await query.answer()

#====================================================#====================================================

# ==================================================================
# 6. HELP MENU & INTERACTIVE GUIDE ANIME (/help)
# ==================================================================

@Client.on_callback_query(filters.regex(r"^anime_(?P<section>[a-z]+)$"))
async def anime_help_callbacks(client, query):
    section = query.matches[0].group("section")
    
    keyboard_back = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Help Menu", callback_data="anime_home", style=ButtonStyle.PRIMARY)]
    ])
    
    if section == "home":
        text = (
            "⛩️ **Anime Scheduler - Help Center**\n\n"
            "Welcome! This bot automatically fetches and posts anime schedule updates to your target chats or channels.\n\n"
            "👇 **Select a category below to learn more:**"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚀 Quick Start", callback_data="anime_quick", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("📋 Commands", callback_data="anime_cmds", style=ButtonStyle.PRIMARY)
            ],
            [
                InlineKeyboardButton("⚙️ Settings Guide", callback_data="anime_settings", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("⏱️ Intervals & Del", callback_data="anime_timers", style=ButtonStyle.PRIMARY)
            ],
            [
                InlineKeyboardButton("❌", callback_data="close", style=ButtonStyle.DANGER),
                InlineKeyboardButton("🔙", callback_data="help_menu", style=ButtonStyle.PRIMARY)
            ]
        ])
        await query.message.edit_text(text, reply_markup=keyboard)
        
    elif section == "quick":
        text = (
            "🚀 **Quick Start Guide**\n\n"
            "1. Open your management panel by sending `/setanime` (or `/setanime chat_id` for groups where you are an admin).\n"
            "2. Toggle **Status: OFF** to turn it **🟢 ON**.\n"
            "3. Configure your frequency intervals and auto-delete timers using the control buttons, and the bot will run automatically!"
        )
        await query.message.edit_text(text, reply_markup=keyboard_back)
        
    elif section == "cmds":
        text = (
            "📋 **Commands Reference**\n\n"
            "• `/setanime` — Open the main interactive configuration panel for your chat/channel.\n"
            "• `/setanime chat_id` — Open the control panel for a specific group or channel (Requires Admin permissions).\n"
            "• `/help` — Open this interactive help center."
        )
        await query.message.edit_text(text, reply_markup=keyboard_back)
        
    elif section == "settings":
        text = (
            "⚙️ **Panel Settings Explained**\n\n"
            "• 🟢/🔴 **Status:** Master toggle to enable or pause automated posting for the chat.\n"
            "• 📌 **Pin:** Automatically pin incoming scheduled anime updates to the top of the chat for high visibility.\n"
            "• ⏱ **Set Interval:** Change how often updates are checked and delivered.\n"
            "• 🗑 **Auto-Delete:** Set a timer to clean up previous posts automatically."
        )
        await query.message.edit_text(text, reply_markup=keyboard_back)
        
    elif section == "timers":
        text = (
            "⏱️ **Intervals & Auto-Delete Guide**\n\n"
            "• **Intervals:** Choose how frequently the bot cycles updates (e.g., 1m, 5m, 20m, 30m, 1h).\n"
            "• **Auto-Delete:** Keep your channel clean by choosing a self-destruction duration (e.g., 30s, 300s, 400s, 2400s, or Turn OFF)."
        )
        await query.message.edit_text(text, reply_markup=keyboard_back)
        
    await query.answer()

# ==================================================================
# HELP MENU & INTERACTIVE GUIDE MODULE ANLYST
# ==================================================================


@Client.on_callback_query(filters.regex(r"^anlyz_(?P<section>[a-z]+)$"))
async def anlyz_help_callbacks(client, query):
    section = query.matches[0].group("section")
    
    keyboard_back = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Help Menu", callback_data="anlyz_home", style=ButtonStyle.PRIMARY)]
    ])
    
    if section == "home":
        text = (
            "📊 **Group Analytics & AI Tools - Help Center**\n\n"
            "Welcome! This bot tracks group activity, ranks top active members, "
            "detects viral spikes, and schedules broadcasts at peak traffic hours.\n\n"
            "👇 **Select a category below to learn more:**"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚀 Quick Start", callback_data="anlyz_quick", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("📋 Commands", callback_data="anlyz_cmds", style=ButtonStyle.PRIMARY)
            ],
            [
                InlineKeyboardButton("🏆 Leaderboard", callback_data="anlyz_leaders", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("🔥 Viral & Golden Hour", callback_data="anlyz_viral", style=ButtonStyle.PRIMARY)
            ],
            [
                InlineKeyboardButton("❌", callback_data="close", style=ButtonStyle.DANGER),
                InlineKeyboardButton("🔙 Back to Home", callback_data="help_menu", style=ButtonStyle.PRIMARY)
            ]
        ])
        await query.message.edit_text(text, reply_markup=keyboard)
        
    elif section == "quick":
        text = (
            "🚀 **Quick Start Guide**\n\n"
            "1. Add the bot to your Telegram group.\n"
            "2. Ensure the bot has permission to read messages so it can record activity data.\n"
            "3. Use `/leaderboard` to check member activity rankings.\n"
            "4. Use `/set_viral_promo` to set up automated messages when the chat gets highly active!"
        )
        await query.message.edit_text(text, reply_markup=keyboard_back)
        
    elif section == "cmds":
        text = (
            "📋 **Commands Reference**\n\n"
            "• `/leaderboard` — Displays top active members for Overall, Today, Week, or Global views.\n"
            "• `/schedule_best [message]` — Schedules a message to automatically post during your group's peak historical activity hour (Golden Hour).\n"
            "• `/set_viral_promo` — **(Reply to a message)** Sets the promotional content to auto-post when chat activity suddenly spikes.\n"
            "• `/anlyzhelp` or `/help` — Opens this help center."
        )
        await query.message.edit_text(text, reply_markup=keyboard_back)
        
    elif section == "leaders":
        text = (
            "🏆 **Leaderboard Features**\n\n"
            "• **Group Overall:** Ranks total messages sent in the current group.\n"
            "• **Today & Week:** Filters rankings by recent member activity.\n"
            "• **Global Ranking:** Compares top active members across all connected groups."
        )
        await query.message.edit_text(text, reply_markup=keyboard_back)
        
    elif section == "viral":
        text = (
            "🔥 **Viral Spikes & Golden Hour Explained**\n\n"
            "• **Golden Hour (`/schedule_best`):** Calculates historical message density by hour and queues your message to post when member engagement is highest.\n"
            "• **Viral Spikes:** Automatically monitors message counts per 5 minutes. If activity exceeds 1.5x your average, the bot broadcasts your pre-configured promo message."
        )
        await query.message.edit_text(text, reply_markup=keyboard_back)
        
    await query.answer()

#====================================================
# ==================================================================
# STANDALONE ANIME SCHEDULER HELP MENU
# ==================================================================


@Client.on_callback_query(filters.regex(r"^anime_(?P<section>[a-z]+)$"))
async def anime_help_callbacks(client, query):
    section = query.matches[0].group("section")
    
    keyboard_back = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Help Menu", callback_data="anime_home", style=ButtonStyle.PRIMARY)]
    ])
    
    if section == "home":
        text = (
            "⛩️ **Anime Scheduler - Help Center**\n\n"
            "Welcome! This bot automatically fetches and posts anime schedule updates to your target chats or channels.\n\n"
            "👇 **Select a category below to learn more:**"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚀 Quick Start", callback_data="anime_quick", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("📋 Commands", callback_data="anime_cmds", style=ButtonStyle.PRIMARY)
            ],
            [
                InlineKeyboardButton("⚙️ Settings Guide", callback_data="anime_set", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("⏱️ Timers & Del", callback_data="anime_timers", style=ButtonStyle.PRIMARY)
            ],
            [
                InlineKeyboardButton("❌", callback_data="close", style=ButtonStyle.DANGER),
                InlineKeyboardButton("🔙", callback_data="help_menu", style=ButtonStyle.PRIMARY)
            ]
        ])
        await query.message.edit_text(text, reply_markup=keyboard)
        
    elif section == "quick":
        text = (
            "🚀 **Quick Start Guide**\n\n"
            "1. Run `/setanime` (or `/setanime chat_id` for groups where you are an admin).\n"
            "2. Click **Status: OFF** to toggle it **🟢 ON**.\n"
            "3. Configure your frequency intervals and auto-delete timers using the control panel, and the bot will run automatically!"
        )
        await query.message.edit_text(text, reply_markup=keyboard_back)
        
    elif section == "cmds":
        text = (
            "📋 **Commands Reference**\n\n"
            "• `/setanime` — Open the main interactive configuration panel.\n"
            "• `/setanime chat_id` — Open the control panel for a specific group/channel.\n"
            "• `/animehelp` — Open this interactive help center."
        )
        await query.message.edit_text(text, reply_markup=keyboard_back)
        
    elif section == "set":
        text = (
            "⚙️ **Panel Settings Explained**\n\n"
            "• 🟢/🔴 **Status:** Master switch to enable or pause automated posting for the chat.\n"
            "• 📌 **Pin:** Automatically pin incoming scheduled anime updates to the top of the chat for high visibility."
        )
        await query.message.edit_text(text, reply_markup=keyboard_back)
        
    elif section == "timers":
        text = (
            "⏱️ **Intervals & Auto-Delete Guide**\n\n"
            "• **Intervals:** Choose how frequently the bot cycles updates (e.g., 1m, 5m, 20m, 30m, 1h).\n"
            "• **Auto-Delete:** Keep your channel clean by choosing a self-destruction duration (e.g., 30s, 300s, 400s, 2400s, or Turn OFF)."
        )
        await query.message.edit_text(text, reply_markup=keyboard_back)
        
    await query.answer()

# ==================================================================
# DEEZER MUSIC BOT - HELP MENU & INTERACTIVE GUIDE (/deezerhelp)
# ==================================================================
from pyrogram.errors import MessageNotModified

@Client.on_callback_query(filters.regex(r"^deez_(?P<section>[a-z]+)$"))
async def deezer_help_callbacks(client, query):
    section = query.matches[0].group("section")
    
    keyboard_back = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Help Menu", callback_data="deez_home", style=ButtonStyle.PRIMARY)]
    ])
    
    try:
        if section == "home":
            text = (
                "🎧 **Deezer Music Schedule Bot - Help Center**\n\n"
                "Welcome! This bot automatically discovers random tracks from Deezer and posts music drops to your target chats or channels at custom intervals.\n\n"
                "👇 **Select a category below to learn more:**"
            )
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🚀 Quick Start", callback_data="deez_quick", style=ButtonStyle.PRIMARY),
                    InlineKeyboardButton("📋 Commands", callback_data="deez_cmds", style=ButtonStyle.PRIMARY)
                ],
                [
                    InlineKeyboardButton("⚙️ Settings Guide", callback_data="deez_set", style=ButtonStyle.PRIMARY),
                    InlineKeyboardButton("⏱️ Intervals & Pin", callback_data="deez_timers", style=ButtonStyle.PRIMARY)
                ],
                [
                    InlineKeyboardButton("❌", callback_data="close", style=ButtonStyle.DANGER),
                    InlineKeyboardButton("🔙", callback_data="help_menu", style=ButtonStyle.PRIMARY)
                ]
            ])
            await query.message.edit_text(text, reply_markup=keyboard)
            
        elif section == "quick":
            text = (
                "🚀 **Quick Start Guide**\n\n"
                "1. Run `/deezertarget chat_id` in your private chat with the bot to configure a group or channel.\n"
                "2. Click **Module: OFF** to toggle it **🟢 ON** (this immediately triggers the first song drop!).\n"
                "3. Customize your interval and auto-pin preferences using the interactive control buttons."
            )
            await query.message.edit_text(text, reply_markup=keyboard_back)
            
        elif section == "cmds":
            text = (
                "📋 **Commands Reference**\n\n"
                "• `/deezertarget chat_id` — Open the interactive configuration dashboard for a specific group or channel.\n"
                "• `/deezerhelp` — Open this interactive help center."
            )
            await query.message.edit_text(text, reply_markup=keyboard_back)
            
        elif section == "set":
            text = (
                "⚙️ **Dashboard Settings Explained**\n\n"
                "• 🟢/🔴 **Module:** Master toggle to turn automated music sharing ON or OFF. Turning it ON resets the timer for an immediate drop.\n"
                "• 📌 **Auto-Pin:** Automatically pins incoming music discovery posts to the top of the chat for high visibility."
            )
            await query.message.edit_text(text, reply_markup=keyboard_back)
            
        elif section == "timers":
            text = (
                "⏱️ **Intervals Guide**\n\n"
                "• **Interval Toggling:** Click the interval button to cycle through preset frequencies: `1m` -> `5m` -> `20m` -> `30m` -> `1h`.\n"
                "• Determines how frequently a new random track is fetched from Deezer and posted to your target chat."
            )
            await query.message.edit_text(text, reply_markup=keyboard_back)
            
    except MessageNotModified:
        pass
        
    await query.answer()


#====================================================
#Footbaoll
#====================================================
@Client.on_callback_query(filters.regex(r"^fob_(?P<section>[a-z]+)$"))
async def food_help_callbacks(client, query):
    section = query.matches[0].group("section")
    
    keyboard_back = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Help Menu", callback_data="fob_home", style=ButtonStyle.PRIMARY)]
    ])
    # Help Sub-menus
    if section == "home":
        help_text = (
            "⚽ **Football Sports Bot - Help Center**\n\n"
            "Welcome! This bot tracks football league standings, fixtures, match results, top scorers, and live schedules.\n\n"
            "👇 **Select a category below to learn more:**"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚀 Quick Start", callback_data="fob_quick", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("📋 Commands", callback_data="fob_cmds", style=ButtonStyle.PRIMARY)
            ],
            [
                InlineKeyboardButton("⚙️ Settings Guide", callback_data="fob_set", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("⭐ Watchlist & Targets", callback_data="fob_team", style=ButtonStyle.PRIMARY)
            ],
            [
                InlineKeyboardButton("❌", callback_data="close", style=ButtonStyle.DANGER),
                InlineKeyboardButton("🔙", callback_data="help_menu", style=ButtonStyle.PRIMARY)
            ]
        ])
        await query.message.edit_text(help_text, reply_markup=keyboard)

    elif section == "quick":
        await query.message.edit_text(
            "🚀 **Quick Start Guide**\n\n"
            "1. Run `/fmatches` to open the interactive dashboard.\n"
            "2. Use the **Date**, **League**, and **Status** selector buttons to filter fixtures instantly.\n"
            "3. Click any **Match #N** button to view deep technical metadata, team crests, half-time scores, and assigned match officials."
            "Another football cmd\n"
            "1. Run `/ftball` to open the main interactive football panel.\n"
            "2. Select Standings, Fixtures, or Results to check live football data.\n"
            "3. Use `/setmyteam` to register your favorite watchlist club.",
            reply_markup=keyboard_back
        )

    elif section == "cmds":
        await query.message.edit_text(
            "📋 **Commands Reference**\n\n"
            "• `/fmatches` — Opens the main interactive football matches dashboard.\n"
            "• `/ftball` — Open the main football dashboard.\n"
            "• `/standings [league]` — View league tables (e.g., PL, CL).\n"
            "• `/fixtures [league]` — View upcoming fixtures.\n"
            "• `/scorers [league]` — Check top goalscorers.\n"
            "• `/today` — View matches happening today.\n"
            "• `/squad <team_id>` — Inspect a team roster.",
            reply_markup=keyboard_back
        )

    elif section == "set":
        await query.message.edit_text(
            "⚙️ **Group Settings & Controls**\n\n"
            "• Configure auto-deletion timers, pin toggles, live match schedules, and toggle active modules via the settings panel (`cfg_menu`).",
            reply_markup=keyboard_back
        )

    elif section == "team":
        await query.message.edit_text(
            "⭐ **Watchlist & Remote Targets**\n\n"
            "• Use `/setmyteam <name>` to save your favorite team.\n"
            "• Use `/ftarget <group_id>` in PM to direct your personal control panel changes to a group chat remotely.",
            reply_markup=keyboard_back
        )
