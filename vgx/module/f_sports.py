import os
import httpx
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config

# --- API FETCH HELPERS ---
async def fetch_from_sportsdb(endpoint: str):
    """Helper to query TheSportsDB API asynchronously using httpx."""
    url = f"{Config.BASE_URL}/{endpoint}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"⚠️ API Connection Error: {str(e)}"}


# --- UI KEYBOARD BUILDERS ---
def get_sports_main_menu():
    """Main interactive hub for TheSportsDB bot module."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Search Team", callback_data="s_menu_team"),
            InlineKeyboardButton("👤 Search Player", callback_data="s_menu_player")
        ],
        [
            InlineKeyboardButton("📊 League Standings", callback_data="s_menu_standings"),
            InlineKeyboardButton("🏆 Browse Leagues", callback_data="s_menu_leagues")
        ],
        [
            InlineKeyboardButton("❌", callback_data="close")
        ]
    ])


# --- COMMAND HANDLERS ---
@app.on_message(filters.command("fsports"))
async def sports_dasgshboard_command(client: Client, message: Message):
    """Command: /sports - Opens the main sports database control panel."""
    welcome_text = (
        "🏅 **TheSportsDB Control Center**\n\n"
        "Welcome! Explore global teams, player bios, stats, badges, and league standings.\n\n"
        "👇 **Select an option below or use commands:**\n"
        "• `/team name` — Lookup club details & badges\n"
        "• `/player name` — Lookup player profile & bio\n"
        "• `/table league_name` — View league standings"
    )
    await message.reply_text(welcome_text, reply_markup=get_sports_main_menu(), parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.command("team"))
async def team_search_command(client: Client, message: Message):
    """Command: /team <team_name> (e.g. /team Arsenal)"""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/team team_name`\nExample: `/team Arsenal`")
    
    query_name = " ".join(args[1:])
    data = await fetch_from_sportsdb(f"searchteams.php?t={query_name}")
    
    if "error" in data:
        return await message.reply_text(data["error"])
        
    teams = data.get("teams")
    if not teams:
        return await message.reply_text(f"❌ No teams found matching **'{query_name}'**.")
        
    team = teams[0] # Take the top result
    name = team.get("strTeam", "N/A")
    sport = team.get("strSport", "N/A")
    country = team.get("strCountry", "N/A")
    formed = team.get("intFormedYear", "N/A")
    stadium = team.get("strStadium", "N/A")
    desc = team.get("strDescriptionEN", "No description available.")[:350] + "..."
    badge = team.get("strBadge")
    banner = team.get("strBanner")
    
    caption = (
        f"🛡️ **Club Profile: {name}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚽ Sport: {sport} | 🌍 Country: {country}\n"
        f"📅 Formed: {formed} | 🏟️ Stadium: {stadium}\n\n"
        f"📝 **Overview:**\n{desc}"
    )
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Hub", callback_data="s_back_home")],
        [InlineKeyboardButton("❌", callback_data="close")]
    ])
    
    # Send photo if badge or banner exists, otherwise send text
    image_url = badge or banner
    if image_url:
        await message.reply_photo(photo=image_url, caption=caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else:
        await message.reply_text(caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.command("player"))
async def player_search_command(client: Client, message: Message):
    """Command: /player <player_name> (e.g. /player Messi)"""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/player player_name`\nExample: `/player Messi`")
    
    query_name = " ".join(args[1:])
    data = await fetch_from_sportsdb(f"searchplayers.php?p={query_name}")
    
    if "error" in data:
        return await message.reply_text(data["error"])
        
    players = data.get("player")
    if not players:
        return await message.reply_text(f"❌ No players found matching **'{query_name}'**.")
        
    player = players[0]
    name = player.get("strPlayer", "N/A")
    team = player.get("strTeam", "N/A")
    sport = player.get("strSport", "N/A")
    nationality = player.get("strNationality", "N/A")
    position = player.get("strPosition", "N/A")
    birthdate = player.get("dateBorn", "N/A")
    thumb = player.get("strThumb")
    cutout = player.get("strCutout")
    
    caption = (
        f"👤 **Player Profile: {name}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ Team: {team} | ⚽ Sport: {sport}\n"
        f"🌍 Nationality: {nationality} | 📌 Position: {position}\n"
        f"🎂 Birthdate: {birthdate}"
    )
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Hub", callback_data="s_back_home")],
        [InlineKeyboardButton("❌", callback_data="close")]
    ])
    
    image_url = cutout or thumb
    if image_url:
        await message.reply_photo(photo=image_url, caption=caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else:
        await message.reply_text(caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


# --- STRICT REGEX CALLBACK ROUTERS ---

@app.on_callback_query(filters.regex(r"^s_back_home$"))
async def cb_sports_home(client: Client, query: CallbackQuery):
    await query.answer()
    welcome_text = (
        "🏅 **TheSportsDB Control Center**\n\n"
        "Welcome! Explore global teams, player bios, stats, badges, and league standings.\n\n"
        "👇 **Select an option below:**"
    )
    await query.message.edit_text(welcome_text, reply_markup=get_sports_main_menu(), parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^s_menu_team$"))
async def cb_menu_team(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(
        "🔍 **Team Search Instructions:**\n\n"
        "To look up a team's stadium, founding year, badge, and overview, use the command:\n"
        "`/team club_name`\n\n"
        "*Example:* `/team Real Madrid` or `/team Arsenal`",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="s_back_home")]]),
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_callback_query(filters.regex(r"^s_menu_player$"))
async def cb_menu_player(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(
        "👤 **Player Search Instructions:**\n\n"
        "To inspect player biographies, birthdates, positions, and cutout graphics, use the command:\n"
        "`/player player_name`\n\n"
        "*Example:* `/player Ronaldo` or `/player LeBron`",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="s_back_home")]]),
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_callback_query(filters.regex(r"^s_menu_standings$"))
async def cb_menu_standings(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(
        "📊 **League Standings Instructions:**\n\n"
        "To query tournament tables and points, use the league search feature or direct API lookup endpoints.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="s_back_home")]]),
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_callback_query(filters.regex(r"^s_menu_leagues$"))
async def cb_menu_leagues(client: Client, query: CallbackQuery):
    await query.answer()
    data = await fetch_from_sportsdb("all_leagues.php")
    if "error" in data:
        return await query.message.edit_text(data["error"])
        
    leagues = data.get("leagues", [])[:10] # Show first 10 for UI layout
    msg = "🏆 **Supported Leagues Directory (Sample):**\n\n"
    for l in leagues:
        msg += f"• **{l.get('strLeague')}** ({l.get('strSport')})\n"
        
    await query.message.edit_text(
        msg,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="s_back_home")]]),
        parse_mode=ParseMode.MARKDOWN
    )


#====================================================

# --- API FETCH HELPERS ---
async def fetch_from_sportsdb(endpoint: str):
    """Helper to query TheSportsDB API asynchronously using httpx."""
    url = f"{Config.BASE_URL}/{endpoint}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"⚠️ API Connection Error: {str(e)}"}


# --- UI KEYBOARD BUILDERS ---
def get_sports_main_menu():
    """Main interactive hub for TheSportsDB bot module."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🛡️ Team Search", callback_data="s_menu_team"),
            InlineKeyboardButton("👤 Player Bio", callback_data="s_menu_player")
        ],
        [
            InlineKeyboardButton("📊 Standings", callback_data="s_menu_standings"),
            InlineKeyboardButton("🎬 Match Highlights", callback_data="s_menu_highlights")
        ],
        [
            InlineKeyboardButton("🏆 Browse Leagues", callback_data="s_menu_leagues"),
            InlineKeyboardButton("❌ Close", callback_data="close")
        ]
    ])


# --- COMMAND HANDLERS ---
@app.on_message(filters.command("fbsports"))
async def sfports_dashboard_command(client: Client, message: Message):
    """Command: /sports - Opens the main sports database control panel."""
    welcome_text = (
        "🏅 **TheSportsDB Master Control Center**\n\n"
        "Welcome! Access global sports data, high-res team badges, player cutouts, standings, and highlights.\n\n"
        "👇 **Use the dashboard or type commands directly:**\n"
        "• `/s_team <name>` — Club details, stadium, and high-res crest\n"
        "• `/s_player <name>` — Player bio, position, and portrait\n"
        "• `/s_table <league_id>` — League standings table\n"
        "• `/s_highlights <team_name>` — Recent match video highlights"
    )
    await message.reply_text(welcome_text, reply_markup=get_sports_main_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("s_team"))
async def teamn_search_command(client: Client, message: Message):
    """Command: /s_team <team_name> (e.g. /s_team Arsenal)"""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/s_team <team_name>`\nExample: `/s_team Arsenal`")
    
    query_name = " ".join(args[1:])
    data = await fetch_from_sportsdb(f"searchteams.php?t={query_name}")
    
    if "error" in data:
        return await message.reply_text(data["error"])
        
    teams = data.get("teams")
    if not teams:
        return await message.reply_text(f"❌ No teams found matching **'{query_name}'**.")
        
    team = teams[0]
    team_id = team.get("idTeam")
    name = team.get("strTeam", "N/A")
    sport = team.get("strSport", "N/A")
    country = team.get("strCountry", "N/A")
    formed = team.get("intFormedYear", "N/A")
    stadium = team.get("strStadium", "N/A")
    desc = team.get("strDescriptionEN", "No description available.")[:300] + "..."
    badge = team.get("strBadge") or team.get("strLogo")
    
    caption = (
        f"🛡️ **Club Profile: {name}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚽ Sport: `{sport}` | 🌍 Country: `{country}`\n"
        f"📅 Formed: `{formed}` | 🏟️ Stadium: `{stadium}`\n\n"
        f"📝 **Overview:**\n{desc}\n\n"
        f"🆔 `Team ID: {team_id}`"
    )
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Next Matches", callback_data=f"s_next_t_{team_id}")],
        [InlineKeyboardButton("⬅️ Back to Hub", callback_data="s_back_home"), InlineKeyboardButton("❌ Close", callback_data="close")]
    ])
    
    if badge:
        await message.reply_photo(photo=badge, caption=caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else:
        await message.reply_text(caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("s_player"))
async def player_search_command(client: Client, message: Message):
    """Command: /s_player <player_name> (e.g. /s_player Messi)"""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/s_player <player_name>`\nExample: `/s_player Messi`")
    
    query_name = " ".join(args[1:])
    data = await fetch_from_sportsdb(f"searchplayers.php?p={query_name}")
    
    if "error" in data:
        return await message.reply_text(data["error"])
        
    players = data.get("player")
    if not players:
        return await message.reply_text(f"❌ No players found matching **'{query_name}'**.")
        
    player = players[0]
    name = player.get("strPlayer", "N/A")
    team = player.get("strTeam", "N/A")
    sport = player.get("strSport", "N/A")
    nationality = player.get("strNationality", "N/A")
    position = player.get("strPosition", "N/A")
    birthdate = player.get("dateBorn", "N/A")
    number = player.get("strNumber", "N/A")
    thumb = player.get("strCutout") or player.get("strThumb") or player.get("strRender")
    
    caption = (
        f"👤 **Player Profile: {name}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ Team: `{team}` | ⚽ Sport: `{sport}`\n"
        f"🌍 Country: `{nationality}` | 📌 Position: `{position}`\n"
        f"🔢 Jersey #: `{number}` | 🎂 Born: `{birthdate}`"
    )
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Hub", callback_data="s_back_home"), InlineKeyboardButton("❌ Close", callback_data="close")]
    ])
    
    if thumb:
        await message.reply_photo(photo=thumb, caption=caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else:
        await message.reply_text(caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("s_table"))
async def standings_command(client: Client, message: Message):
    """Command: /s_table <league_id> (e.g. /s_table 4328)"""
    args = message.command
    league_id = args[1] if len(args) > 1 else "4328"  # Default: Premier League (4328)
    
    data = await fetch_from_sportsdb(f"lookuptable.php?l={league_id}")
    if "error" in data:
        return await message.reply_text(data["error"])
        
    table = data.get("table", [])
    if not table:
        return await message.reply_text(f"❌ No standings data found for League ID `{league_id}`.")
        
    msg = f"📊 **League Table Standings (ID: {league_id})**\n\n"
    msg += "`#  | Team           | P | Pts | GD`\n"
    msg += "`----------------------------------`\n"
    
    for row in table[:15]:
        pos = str(row.get('intRank', '-')).ljust(2)
        team = str(row.get('strTeam', 'Team'))[:14].ljust(14)
        played = str(row.get('intPlayed', '0')).ljust(2)
        pts = str(row.get('intPoints', '0')).ljust(3)
        gd = str(row.get('intGoalDifference', '0')).ljust(3)
        msg += f"`{pos} | {team} | {played} | {pts} | {gd}`\n"
        
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Hub", callback_data="s_back_home")]])
    await message.reply_text(msg, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


# --- STRICT REGEX CALLBACK ROUTERS ---

@app.on_callback_query(filters.regex(r"^s_back_home$"))
async def cb_sports_home(client: Client, query: CallbackQuery):
    await query.answer()
    welcome_text = (
        "🏅 **TheSportsDB Master Control Center**\n\n"
        "Welcome! Access global sports data, high-res team badges, player cutouts, standings, and highlights.\n\n"
        "👇 **Select an option below:**"
    )
    await query.message.edit_text(welcome_text, reply_markup=get_sports_main_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^s_menu_team$"))
async def cb_menu_team(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(
        "🔍 **Search Team:**\n\nSend `/s_team <club_name>` in chat to inspect any team globally.\n\n*Example:* `/s_team Real Madrid`",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="s_back_home")]]),
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^s_menu_player$"))
async def cb_menu_player(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(
        "👤 **Search Player:**\n\nSend `/s_player <name>` in chat to view player cutout artwork and bios.\n\n*Example:* `/s_player Messi`",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="s_back_home")]]),
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^s_menu_standings$"))
async def cb_menu_standings(client: Client, query: CallbackQuery):
    await query.answer()
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏴󠁧󠁢󠁥󠁮󠁧󠁿 EPL (4328)", callback_data="s_tbl_4328"),
            InlineKeyboardButton("🇪🇸 La Liga (4335)", callback_data="s_tbl_4335")
        ],
        [
            InlineKeyboardButton("🇩🇪 Bundesliga (4331)", callback_data="s_tbl_4331"),
            InlineKeyboardButton("🇮🇹 Serie A (4332)", callback_data="s_tbl_4332")
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="s_back_home")]
    ])
    await query.message.edit_text("📊 **Select a popular league table to inspect:**", reply_markup=kb)


@app.on_callback_query(filters.regex(r"^s_tbl_(?P<lid>\d+)$"))
async def cb_table_lookup(client: Client, query: CallbackQuery):
    await query.answer("Fetching table...")
    league_id = query.matches[0].group("lid")
    data = await fetch_from_sportsdb(f"lookuptable.php?l={league_id}")
    
    if "error" in data:
        return await query.message.edit_text(data["error"])
        
    table = data.get("table", [])
    if not table:
        return await query.message.edit_text(f"❌ No standings data found for League ID `{league_id}`.")
        
    msg = f"📊 **League Table Standings (ID: {league_id})**\n\n"
    msg += "`#  | Team           | P | Pts | GD`\n"
    msg += "`----------------------------------`\n"
    
    for row in table[:15]:
        pos = str(row.get('intRank', '-')).ljust(2)
        team = str(row.get('strTeam', 'Team'))[:14].ljust(14)
        played = str(row.get('intPlayed', '0')).ljust(2)
        pts = str(row.get('intPoints', '0')).ljust(3)
        gd = str(row.get('intGoalDifference', '0')).ljust(3)
        msg += f"`{pos} | {team} | {played} | {pts} | {gd}`\n"
        
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Leagues", callback_data="s_menu_standings")]])
    await query.message.edit_text(msg, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^s_next_t_(?P<tid>\d+)$"))
async def cb_next_team_events(client: Client, query: CallbackQuery):
    await query.answer("Fetching upcoming fixtures...")
    team_id = query.matches[0].group("tid")
    data = await fetch_from_sportsdb(f"eventsnext.php?id={team_id}")
    
    if "error" in data:
        return await query.answer(data["error"], show_alert=True)
        
    events = data.get("events", [])
    if not events:
        return await query.message.reply_text(f"❌ No upcoming scheduled fixtures found for Team ID `{team_id}`.")
        
    msg = f"📅 **Upcoming Fixtures for Team ID {team_id}:**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for e in events[:5]:
        date = e.get("dateEvent", "N/A")
        time = e.get("strTime", "N/A")[:5]
        event_name = e.get("strEvent", "Match")
        league = e.get("strLeague", "League")
        msg += f"• `{date} {time}` ({league})\n  ⚽ **{event_name}**\n\n"
        
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Hub", callback_data="s_back_home")]])
    await query.message.reply_text(msg, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^s_menu_leagues$"))
async def cb_menu_leagues(client: Client, query: CallbackQuery):
    await query.answer("Fetching sample directory...")
    data = await fetch_from_sportsdb("all_leagues.php")
    if "error" in data:
        return await query.message.edit_text(data["error"])
        
    leagues = data.get("leagues", [])[:10]
    msg = "🏆 **Supported Leagues Directory (Sample):**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for l in leagues:
        msg += f"• **{l.get('strLeague')}** (`{l.get('strSport')}`)\n"
        
    await query.message.edit_text(
        msg,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="s_back_home")]]),
        parse_mode=ParseMode.MARKDOWN
    )
