import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config

# --- CONFIGURATION ---
BRAWLSTARS_BASE_URL = "https://api.brawlstars.com/v1"


def safe_truncate(text: str, max_length: int = 3800) -> str:
    """Safely truncates text to stay well within Telegram's 4000 character limit."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n\n... _(Output truncated due to length limitations)_"


async def brawlstars_request(endpoint: str, params: dict = None) -> dict:
    """Helper utility for asynchronous requests to the official Brawl Stars API via httpx."""
    api_key = getattr(Config, 'BRAWLSTARS_API_KEY')
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    # URL encode '#' symbols in tags (e.g. #2R20PL0UR -> %232R20PL0UR)
    cleaned_endpoint = endpoint.replace("#", "%23")
    url = f"{BRAWLSTARS_BASE_URL.rstrip('/')}/{cleaned_endpoint.lstrip('/')}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "status": response.status_code, "error": safe_truncate(response.text, max_length=1500)}
        except Exception as e:
            return {"success": False, "status": 500, "error": str(e)}


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_brawlstars_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for Brawl Stars API controls."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Player Stats", callback_data="bs_menu_player"),
            InlineKeyboardButton("⚔️ Battle Log", callback_data="bs_menu_battles")
        ],
        [
            InlineKeyboardButton("🛡️ Club Info", callback_data="bs_menu_club"),
            InlineKeyboardButton("🏆 Leaderboards", callback_data="bs_menu_rankings")
        ],
        [
            InlineKeyboardButton("🤖 Brawlers List", callback_data="bs_brawlers"),
            InlineKeyboardButton("🗺️ Events Rotation", callback_data="bs_events")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="bs_close")]
    ])


@app.on_message(filters.command(["brawlstars", "bs", "brawl"]))
async def cmd_brawlstars_dashboard(client: Client, message: Message):
    """Command: /brawlstars - Opens the master interactive Brawl Stars API command suite."""
    text = (
        "⭐ **Brawl Stars Intelligence Suite**\n\n"
        "Query player profiles, battle logs, club rosters, global leaderboards, brawlers, and active event maps instantly.\n\n"
        "👉 **Use the buttons below or quick commands:**\n"
        "• `/bsplayer <tag>`\n"
        "• `/bsclub <tag>`\n"
        "• `/bsbattles <tag>`"
    )
    await message.reply_text(safe_truncate(text), reply_markup=get_brawlstars_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.command(["bsplayer", "player"]))
async def cmd_bs_player(client: Client, message: Message):
    """Command: /bsplayer <tag> - Retrieves player stats."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/bsplayer #TAG`\n_Example:_ `/bsplayer #8CG8LUJ`", parse_mode=ParseMode.MARKDOWN)

    tag = args[1].strip()
    msg = await message.reply_text(f"🔍 Fetching player profile for `{tag}`...")

    res = await brawlstars_request(f"players/{tag}")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="bs_home")]])

    if not res["success"]:
        return await msg.edit_text(
            f"❌ **API Request Failed** (`{res.get('status', 500)}`):\n`{safe_truncate(res['error'])}`\n\n"
            "_Tip: Check your API key and ensure your static IP/proxy is correctly whitelisted in the Supercell Developer Portal._",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

    p = res["data"]
    text = (
        f"👤 **PLAYER PROFILE: {p.get('name', 'Unknown')}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Tag:** `{p.get('tag')}`\n"
        f"• **Trophies:** 🏆 `{p.get('trophies', 0)}` (Highest: `{p.get('highestTrophies', 0)}`)\n"
        f"• **Solo Victories:** 🥇 `{p.get('soloVictories', 0)}`\n"
        f"• **Duo Victories:** 🥈 `{p.get('duoVictories', 0)}`\n"
        f"• **3vs3 Victories:** 🎮 `{p.get('3vs3Victories', 0)}`\n"
        f"• **Club:** `{p.get('club', {}).get('name', 'None')}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await msg.edit_text(safe_truncate(text), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["bsclub", "club"]))
async def cmd_bs_club(client: Client, message: Message):
    """Command: /bsclub <tag> - Retrieves club info and member roster."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/bsclub #TAG`\n_Example:_ `/bsclub #2RJLGLJ`", parse_mode=ParseMode.MARKDOWN)

    tag = args[1].strip()
    msg = await message.reply_text(f"🔍 Fetching club info for `{tag}`...")

    res = await brawlstars_request(f"clubs/{tag}")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="bs_home")]])

    if not res["success"]:
        return await msg.edit_text(f"❌ **Error:**\n`{safe_truncate(res['error'])}`", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    c = res["data"]
    members = c.get("members", [])
    members_preview = ", ".join([m.get("name", "") for m in members[:5]])

    text = (
        f"🛡️ **CLUB: {c.get('name', 'Unknown')}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Tag:** `{c.get('tag')}`\n"
        f"• **Description:** _{c.get('description', 'No description')}_\n"
        f"• **Trophies:** 🏆 `{c.get('trophies', 0)}`\n"
        f"• **Members:** 👥 `{len(members)} / 30`\n"
        f"• **Top Members:** `{members_preview} ...`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await msg.edit_text(safe_truncate(text), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["bsbattles", "battles"]))
async def cmd_bs_battles(client: Client, message: Message):
    """Command: /bsbattles <tag> - Retrieves player battle logs."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/bsbattles #TAG`", parse_mode=ParseMode.MARKDOWN)

    tag = args[1].strip()
    msg = await message.reply_text(f"🔍 Fetching battle logs for `{tag}`...")

    res = await brawlstars_request(f"players/{tag}/battlelog")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="bs_home")]])

    if not res["success"]:
        return await msg.edit_text(f"❌ **Error:**\n`{safe_truncate(res['error'])}`", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    items = res.get("data", {}).get("items", [])
    if not items:
        return await msg.edit_text("📭 No recent battle records found.", reply_markup=keyboard)

    output = [f"⚔️ **RECENT BATTLES FOR `{tag}`**\n━━━━━━━━━━━━━━━━━━━━━━"]
    for idx, b in enumerate(items[:5], start=1):
        battle = b.get("battle", {})
        mode = b.get("event", {}).get("mode", "Unknown Mode")
        result = battle.get("result", battle.get("rank", "Completed"))
        output.append(f"**{idx}. Mode:** `{mode}` | **Result:** `{result}`")

    await msg.edit_text(safe_truncate("\n".join(output)), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["bsbrawlers", "brawlers"]))
async def cmd_bs_brawlers(client: Client, message: Message):
    """Command: /bsbrawlers - Lists all brawlers and attributes."""
    msg = await message.reply_text("🔍 Fetching Brawler catalog...")
    res = await brawlstars_request("brawlers")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="bs_home")]])

    if not res["success"]:
        return await msg.edit_text(f"❌ **Error:**\n`{safe_truncate(res['error'])}`", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    brawlers = res.get("data", {}).get("items", [])
    output = [f"🤖 **BRAWLERS CATALOG ({len(brawlers)})**\n━━━━━━━━━━━━━━━━━━━━━━"]
    for b in brawlers[:15]:
        output.append(f"• **{b.get('name')}** (ID: `{b.get('id')}`)")

    await msg.edit_text(safe_truncate("\n".join(output)), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["bsevents", "events"]))
async def cmd_bs_events(client: Client, message: Message):
    """Command: /bsevents - Retrieves current event rotation maps."""
    msg = await message.reply_text("🔍 Fetching active events rotation...")
    res = await brawlstars_request("events/rotation")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="bs_home")]])

    if not res["success"]:
        return await msg.edit_text(f"❌ **Error:**\n`{safe_truncate(res['error'])}`", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    events = res.get("data", [])
    output = [f"🗺️ **ACTIVE EVENTS ROTATION**\n━━━━━━━━━━━━━━━━━━━━━━"]
    for ev in events[:5]:
        mode = ev.get("event", {}).get("mode", "Mode")
        map_name = ev.get("event", {}).get("map", "Map")
        output.append(f"• **{mode}** — _{map_name}_")

    await msg.edit_text(safe_truncate("\n".join(output)), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^bs_home$"))
async def cb_bs_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "⭐ **Brawl Stars Intelligence Suite**\n\n"
        "Query player profiles, battle logs, club rosters, global leaderboards, brawlers, and active event maps instantly."
    )
    await query.message.edit_text(safe_truncate(text), reply_markup=get_brawlstars_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^bs_menu_player$"))
async def cb_bs_menu_player(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="bs_home")]])
    await query.message.edit_text(
        "👤 **Player Stats Guide:**\n\nSend command in chat:\n`/bsplayer #TAG`\n\n_Example:_ `/bsplayer #8CG8LUJ`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^bs_menu_battles$"))
async def cb_bs_menu_battles(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="bs_home")]])
    await query.message.edit_text(
        "⚔️ **Battle Log Guide:**\n\nSend command in chat:\n`/bsbattles #TAG`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^bs_menu_club$"))
async def cb_bs_menu_club(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="bs_home")]])
    await query.message.edit_text(
        "🛡️ **Club Info Guide:**\n\nSend command in chat:\n`/bsclub #TAG`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^bs_menu_rankings$"))
async def cb_bs_menu_rankings(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="bs_home")]])
    await query.message.edit_text(
        "🏆 **Rankings Endpoint:**\n\nAccess global or country rankings using endpoint:\n`rankings/{countryCode}/players` or `rankings/{countryCode}/clubs`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^bs_brawlers$"))
async def cb_bs_brawlers(client: Client, query: CallbackQuery):
    await query.answer("Fetching brawlers...")
    res = await brawlstars_request("brawlers")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="bs_home")]])
    if not res["success"]:
        return await query.message.edit_text(f"❌ Error: `{safe_truncate(res['error'])}`", reply_markup=keyboard)

    brawlers = res.get("data", {}).get("items", [])
    output = [f"🤖 **BRAWLERS LIST**\n━━━━━━━━━━━━━━━━━━━━━━"]
    for b in brawlers[:12]:
        output.append(f"• **{b.get('name')}**")
    await query.message.edit_text(safe_truncate("\n".join(output)), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^bs_events$"))
async def cb_bs_events(client: Client, query: CallbackQuery):
    await query.answer("Fetching events...")
    res = await brawlstars_request("events/rotation")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="bs_home")]])
    if not res["success"]:
        return await query.message.edit_text(f"❌ Error: `{safe_truncate(res['error'])}`", reply_markup=keyboard)

    events = res.get("data", [])
    output = [f"🗺️ **ACTIVE MAP ROTATION**\n━━━━━━━━━━━━━━━━━━━━━━"]
    for ev in events[:5]:
        mode = ev.get("event", {}).get("mode", "Mode")
        map_name = ev.get("event", {}).get("map", "Map")
        output.append(f"• **{mode}** — _{map_name}_")
    await query.message.edit_text(safe_truncate("\n".join(output)), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^bs_close$"))
async def cb_bs_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
