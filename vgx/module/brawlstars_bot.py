import httpx
from bs4 import BeautifulSoup
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app

# --- IN-MEMORY ROSTER STORAGE (Can be replaced with a database) ---
TRACKED_PLAYERS = {
    "9C98R9Q00": "Player One",
    "8CG8LUJ": "Player Two"
}


def safe_truncate(text: str, max_length: int = 3800) -> str:
    """Safely truncates text to stay well within Telegram's 4000 character limit."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n\n... _(Output truncated due to length limitations)_"


async def scrape_player_stats(tag: str) -> dict:
    """Helper function to fetch and scrape player info from Brawlify public profile."""
    clean_tag = tag.replace("#", "").strip()
    url = f"https://brawlify.com/player/{clean_tag}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}

            soup = BeautifulSoup(response.text, "html.parser")
            title_tag = soup.find("title")
            title = title_tag.text.strip() if title_tag else "Brawl Stars Profile"

            return {"success": True, "title": title, "url": url}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_roster_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for multi-player tracking."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 View All Tracked Players", callback_data="bs_roster_list"),
            InlineKeyboardButton("➕ Add Player Tag", callback_data="bs_roster_add_help")
        ],
        [
            InlineKeyboardButton("🔄 Check All Roster Stats", callback_data="bs_roster_check_all"),
            InlineKeyboardButton("❌ Close", callback_data="bs_close")
        ]
    ])


@app.on_message(filters.command(["roster", "bsroster", "playertags"]))
async def cmd_brawl_roster(client: Client, message: Message):
    """Command: /roster - Opens the multi-player roster management suite."""
    text = (
        "⭐ **Brawl Stars Multi-Player Roster Suite**\n\n"
        f"Currently tracking **{len(TRACKED_PLAYERS)}** player tags.\n\n"
        "👉 **Quick Commands:**\n"
        "• `/addtag <#TAG> <Name>` — Add a new player\n"
        "• `/removetag <#TAG>` — Remove a player\n"
        "• `/allstats` — Fetch live stats for all saved players"
    )
    await message.reply_text(safe_truncate(text), reply_markup=get_roster_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- ROSTER MANAGEMENT COMMANDS ---
# ==========================================

@app.on_message(filters.command(["addtag"]))
async def cmd_add_tag(client: Client, message: Message):
    """Command: /addtag <#TAG> <Name> - Adds a player tag to the tracking roster."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/addtag #9C98R9Q00 PlayerName`", parse_mode=ParseMode.MARKDOWN)

    tag = args[1].replace("#", "").strip().upper()
    name = " ".join(args[2:]) if len(args) > 2 else f"Player_{tag}"

    TRACKED_PLAYERS[tag] = name
    await message.reply_text(f"✅ Successfully added **{name}** (`#{tag}`) to the roster!\nTotal tracked: `{len(TRACKED_PLAYERS)}`", parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["removetag"]))
async def cmd_remove_tag(client: Client, message: Message):
    """Command: /removetag <#TAG> - Removes a player tag from the roster."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/removetag #9C98R9Q00`", parse_mode=ParseMode.MARKDOWN)

    tag = args[1].replace("#", "").strip().upper()
    if tag in TRACKED_PLAYERS:
        name = TRACKED_PLAYERS.pop(tag)
        await message.reply_text(f"🗑️ Removed **{name}** (`#{tag}`) from the roster.", parse_mode=ParseMode.MARKDOWN)
    else:
        await message.reply_text(f"⚠️ Tag `#{tag}` was not found in the roster.", parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["allstats", "checkroster"]))
async def cmd_check_all_stats(client: Client, message: Message):
    """Command: /allstats - Scrapes and displays status for all players in the roster."""
    if not TRACKED_PLAYERS:
        return await message.reply_text("📭 Roster is empty! Use `/addtag #TAG Name` to add players.")

    msg = await message.reply_text(f"🔄 Fetching public stats for all {len(TRACKED_PLAYERS)} players...")
    
    output = [f"📊 **BRAWL STARS ROSTER STATUS**\n━━━━━━━━━━━━━━━━━━━━━━"]
    
    for tag, name in TRACKED_PLAYERS.items():
        res = await scrape_player_stats(tag)
        if res["success"]:
            output.append(f"• **{name}** (`#{tag}`)\n   └ _Status:_ Active | [View Profile]({res['url']})")
        else:
            output.append(f"• **{name}** (`#{tag}`)\n   └ _Status:_ Error fetching profile")

    output.append("━━━━━━━━━━━━━━━━━━━━━━")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="bs_roster_home")]])
    
    await msg.edit_text(safe_truncate("\n".join(output)), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^bs_roster_home$"))
async def cb_roster_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "⭐ **Brawl Stars Multi-Player Roster Suite**\n\n"
        f"Currently tracking **{len(TRACKED_PLAYERS)}** player tags."
    )
    await query.message.edit_text(safe_truncate(text), reply_markup=get_roster_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^bs_roster_list$"))
async def cb_roster_list(client: Client, query: CallbackQuery):
    await query.answer("Loading player roster...")
    if not TRACKED_PLAYERS:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="bs_roster_home")]])
        return await query.message.edit_text("📭 Roster is currently empty.", reply_markup=keyboard)

    output = [f"📋 **TRACKED PLAYERS LIST ({len(TRACKED_PLAYERS)})**\n━━━━━━━━━━━━━━━━━━━━━━"]
    for tag, name in TRACKED_PLAYERS.items():
        output.append(f"• **{name}**: `#{tag}`")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Check All Stats", callback_data="bs_roster_check_all")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="bs_roster_home")]
    ])
    await query.message.edit_text(safe_truncate("\n".join(output)), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^bs_roster_check_all$"))
async def cb_roster_check_all(client: Client, query: CallbackQuery):
    await query.answer("Scraping roster stats...", show_alert=False)
    if not TRACKED_PLAYERS:
        return

    output = [f"📊 **BULK ROSTER LIVE CHECK**\n━━━━━━━━━━━━━━━━━━━━━━"]
    for tag, name in TRACKED_PLAYERS.items():
        res = await scrape_player_stats(tag)
        if res["success"]:
            output.append(f"• **{name}** (`#{tag}`)\n   └ [Open Profile]({res['url']})")
        else:
            output.append(f"• **{name}** (`#{tag}`): Failed")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="bs_roster_home")]])
    await query.message.edit_text(safe_truncate("\n".join(output)), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


@app.on_callback_query(filters.regex(r"^bs_roster_add_help$"))
async def cb_roster_add_help(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="bs_roster_home")]])
    text = (
        "➕ **How to Add Players:**\n\n"
        "Send the following command in chat to add any tag to your list:\n"
        "`/addtag #9C98R9Q00 MyFriend`\n\n"
        "You can add as many player tags as you want!"
    )
    await query.message.edit_text(safe_truncate(text), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^bs_close$"))
async def cb_roster_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
