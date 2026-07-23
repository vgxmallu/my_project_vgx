import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from config import Config
from vgx import app


#====================================================
#====================================================
#====================================================
from vgx.database.footdb import get_cached_api, set_cached_api, save_user

HEADERS = {
    "x-apisports-key": Config.API_FOOTBALL_KEY,
    "x-apisports-host": "https://v3.football.api-sports.io"
}


async def fetch_api(endpoint: str, params: dict = None, cache_ttl: int = 1800) -> dict:
    """Async wrapper for API-Football with MongoDB caching."""
    param_str = "_".join([f"{k}:{v}" for k, v in sorted(params.items())]) if params else "none"
    cache_key = f"{endpoint}_{param_str}"

    cached = await get_cached_api(cache_key)
    if cached:
        return cached

    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            response = await client.get(f"{config.BASE_URL}/{endpoint}", headers=HEADERS, params=params)
            if response.status_code == 200:
                data = response.json()
                if data.get("response"):
                    await set_cached_api(cache_key, data, ttl_seconds=cache_ttl)
                return data
        except Exception:
            pass
    return {}

# --- FEATURE ENDPOINTS ---

async def get_live_scores():
    data = await fetch_api("fixtures", params={"live": "all"}, cache_ttl=120) # 2-min cache
    results = data.get("response", [])
    if not results:
        return "😴 **No live matches ongoing right now.**"

    lines = ["🔴 **CURRENT LIVE MATCHES**\n"]
    for item in results[:12]:
        home = item['teams']['home']['name']
        away = item['teams']['away']['name']
        gh = item['goals']['home']
        ga = item['goals']['away']
        m = item['fixture']['status']['elapsed']
        lines.append(f"• **{home}** `{gh}` - `{ga}` **{away}** ({m}')")
    return "\n".join(lines)

async def get_standings(league_id: int):
    season = config.get_current_season()
    data = await fetch_api("standings", params={"league": league_id, "season": season}, cache_ttl=21600)
    try:
        table = data["response"][0]["league"]["standings"][0]
        league_name = data["response"][0]["league"]["name"]
        
        msg = f"🏆 **{league_name} Standings ({season}/{season+1})**\n\n"
        msg += "`Pos | Team            | Pts | GD`\n"
        msg += "`--------------------------------`\n"
        for t in table[:10]:
            rank = str(t['rank']).rjust(2)
            name = t['team']['name'][:14].ljust(14)
            pts = str(t['points']).rjust(3)
            gd = str(t['goalsDiff']).rjust(3)
            msg += f"`{rank}  | {name} | {pts} | {gd}`\n"
        return msg
    except Exception:
        return "⚠️ Standings currently unavailable."

async def get_top_scorers(league_id: int):
    season = config.get_current_season()
    data = await fetch_api("players/topscorers", params={"league": league_id, "season": season}, cache_ttl=21600)
    results = data.get("response", [])
    if not results:
        return "⚠️ Top scorers data unavailable."

    lines = [f"🎯 **TOP SCORERS ({season}/{season+1})**\n"]
    for idx, item in enumerate(results[:10], start=1):
        player = item['player']['name']
        team = item['statistics'][0]['team']['name']
        goals = item['statistics'][0]['goals']['total'] or 0
        lines.append(f"{idx}. **{player}** ({team}) — ⚽ `{goals}` Goals")
    return "\n".join(lines)

async def get_match_prediction(fixture_id: int):
    data = await fetch_api("predictions", params={"fixture": fixture_id}, cache_ttl=43200)
    try:
        pred = data["response"][0]["predictions"]
        teams = data["response"][0]["teams"]
        home, away = teams["home"]["name"], teams["away"]["name"]
        
        msg = f"🔮 **Match Prediction: {home} vs {away}**\n\n"
        msg += f"💡 **Advice:** `{pred['advice']}`\n\n"
        msg += f"📊 **Win Probabilities:**\n"
        msg += f"• {home}: `{pred['percent']['home']}`\n"
        msg += f"• Draw: `{pred['percent']['draw']}`\n"
        msg += f"• {away}: `{pred['percent']['away']}`\n"
        return msg
    except Exception:
        return "⚠️ Prediction data unavailable for this fixture."

async def get_lineups(fixture_id: int):
    data = await fetch_api("fixtures/lineups", params={"fixture": fixture_id}, cache_ttl=3600)
    lineups = data.get("response", [])
    if not lineups:
        return "⏳ **Lineups are usually confirmed 1 hour before kickoff.**"

    msg = "📋 **Confirmed Lineups**\n\n"
    for team_data in lineups:
        team_name = team_data["team"]["name"]
        formation = team_data["formation"] or "N/A"
        coach = team_data["coach"]["name"] or "N/A"
        
        msg += f"🛡 **{team_name}** (`{formation}`)\n"
        msg += f"👔 Coach: {coach}\n🟢 **Starting XI:**\n"
        for p in team_data["startXI"][:11]:
            msg += f"  • `#{p['player']['number']}` {p['player']['name']} ({p['player']['pos']})\n"
        msg += "──────────────\n"
    return msg

async def get_injuries(fixture_id: int):
    data = await fetch_api("injuries", params={"fixture": fixture_id}, cache_ttl=14400)
    injuries = data.get("response", [])
    if not injuries:
        return "✅ **No major injuries or absences reported for this fixture.**"

    msg = "🏥 **Injury & Absence Report**\n\n"
    for item in injuries:
        player = item["player"]["name"]
        team = item["team"]["name"]
        reason = item["player"]["reason"]
        msg += f"• **{player}** ({team})\n  ⚠️ `{reason}`\n"
    return msg

async def get_head_to_head(team1_id: int, team2_id: int):
    data = await fetch_api("fixtures/headtohead", params={"h2h": f"{team1_id}-{team2_id}", "last": 5}, cache_ttl=43200)
    matches = data.get("response", [])
    if not matches:
        return "❌ No recent head-to-head history found."

    msg = "⚔️ **Last 5 Head-to-Head Matches**\n\n"
    for item in matches:
        date = item["fixture"]["date"][:10]
        home = item["teams"]["home"]["name"]
        away = item["teams"]["away"]["name"]
        gh, ga = item["goals"]["home"], item["goals"]["away"]
        msg += f"🗓 `{date}` | {home} **{gh} - {ga}** {away}\n"
    return msg


def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔴 Live Scores", callback_data="af_live"),
            InlineKeyboardButton("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", callback_data="af_league_39")
        ],
        [
            InlineKeyboardButton("🇪🇸 La Liga", callback_data="af_league_140"),
            InlineKeyboardButton("🇮🇹 Serie A", callback_data="af_league_135")
        ],
        [
            InlineKeyboardButton("🇩🇪 Bundesliga", callback_data="af_league_78"),
            InlineKeyboardButton("🇪🇺 Champions League", callback_data="af_league_2")
        ]
    ])

def league_menu_keyboard(league_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Standings", callback_data=f"af_standings_{league_id}"),
            InlineKeyboardButton("🎯 Top Scorers", callback_data=f"af_topscorers_{league_id}")
        ],
        [
            InlineKeyboardButton("⬅️ Main Menu", callback_data="af_main")
        ]
    ])

def fixture_details_keyboard(fixture_id: int, team1_id: int = None, team2_id: int = None):
    buttons = [
        [
            InlineKeyboardButton("🔮 AI Prediction", callback_data=f"af_predict_{fixture_id}"),
            InlineKeyboardButton("📋 Lineups", callback_data=f"af_lineup_{fixture_id}")
        ],
        [
            InlineKeyboardButton("🏥 Injuries", callback_data=f"af_injuries_{fixture_id}")
        ]
    ]
    if team1_id and team2_id:
        buttons[1].append(InlineKeyboardButton("⚔️ H2H History", callback_data=f"af_h2h_{team1_id}-{team2_id}"))

    buttons.append([InlineKeyboardButton("⬅️ Main Menu", callback_data="af_main")])
    return InlineKeyboardMarkup(buttons)

def back_to_main():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Main Menu", callback_data="af_main")]])



    # --- COMMAND HANDLERS ---
@app.on_message(filters.command("football"))
def starhhd(client: Client, message: Message):
    if not message.from_user:
        return
    await save_user(message.from_user.id, message.from_user.username or "Unknown")
    await message.reply_text(
        "⚽ **Ultimate API-Football Bot**\n\n"
        "Choose a league or query option below:",
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_message(filters.command("predict"))
def predivvct_cmd(client: Client, message: Message):
    if not message.from_user:
        return
    args = message.command
    if len(args) < 2:
        await message.reply_text("⚠️ **Usage:** `/predict <fixture_id>`\nExample: `/predict 1035088`")
        return
        
    fixture_id = int(args[1])
    res = await get_match_prediction(fixture_id)
    await message.reply_text(res, reply_markup=fixture_details_keyboard(fixture_id), parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.command("h2h"))
def h2h_cmd(client: Client, message: Message):
    if not message.from_user:
        return
    args = message.command
    if len(args) < 3:
        await message.reply_text("⚠️ **Usage:** `/h2h <team1_id> <team2_id>`\nExample: `/h2h 33 34`")
        return
        
    t1, t2 = int(args[1]), int(args[2])
    res = await get_head_to_head(t1, t2)
    await message.reply_text(res, reply_markup=back_to_main(), parse_mode=ParseMode.MARKDOWN)


    # 🎯 UNIVERSAL REGEX CALLBACK ROUTER
    # Intercepts all callbacks starting with 'af_' using group capturing
@app.on_callback_query(filters.regex(r"^af_(main|live|league|standings|topscorers|predict|lineup|injuries|h2h)(?:_(.+))?$"))
def callbgack_router(client: Client, query: CallbackQuery):
    await query.answer()
    if not query.from_user:
        return

    await save_user(query.from_user.id, query.from_user.username or "Unknown")

    action = query.matches[0].group(1)
    param = query.matches[0].group(2) # Optional parameter string

    try:
        if action == "main":
            await query.message.edit_text(
                "⚽ **Ultimate API-Football Bot**\n\nChoose an option below:",
                reply_markup=main_menu_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )

        elif action == "live":
            await query.message.edit_text("⏳ **Fetching live scores...**")
            res = await get_live_scores()
            await query.message.edit_text(res, reply_markup=back_to_main(), parse_mode=ParseMode.MARKDOWN)

        elif action == "league":
            league_id = int(param)
            await query.message.edit_text(
                f"🏆 **League Options (ID: {league_id})**\nSelect statistics category:",
                reply_markup=league_menu_keyboard(league_id),
                parse_mode=ParseMode.MARKDOWN
            )

        elif action == "standings":
            league_id = int(param)
            await query.message.edit_text("⏳ **Fetching Standings...**")
            res = await get_standings(league_id)
            await query.message.edit_text(res, reply_markup=league_menu_keyboard(league_id), parse_mode=ParseMode.MARKDOWN)

        elif action == "topscorers":
            league_id = int(param)
            await query.message.edit_text("⏳ **Fetching Top Scorers...**")
            res = await get_top_scorers(league_id)
            await query.message.edit_text(res, reply_markup=league_menu_keyboard(league_id), parse_mode=ParseMode.MARKDOWN)

        elif action == "predict":
            fixture_id = int(param)
            await query.message.edit_text("⏳ **Analyzing Match Predictions...**")
            res = await get_match_prediction(fixture_id)
            await query.message.edit_text(res, reply_markup=fixture_details_keyboard(fixture_id), parse_mode=ParseMode.MARKDOWN)

        elif action == "lineup":
            fixture_id = int(param)
            await query.message.edit_text("⏳ **Fetching Lineups...**")
            res = await get_lineups(fixture_id)
            await query.message.edit_text(res, reply_markup=fixture_details_keyboard(fixture_id), parse_mode=ParseMode.MARKDOWN)

        elif action == "injuries":
            fixture_id = int(param)
            await query.message.edit_text("⏳ **Checking Injury Reports...**")
            res = await get_injuries(fixture_id)
            await query.message.edit_text(res, reply_markup=fixture_details_keyboard(fixture_id), parse_mode=ParseMode.MARKDOWN)

        elif action == "h2h":
            t1, t2 = map(int, param.split("-"))
            await query.message.edit_text("⏳ **Loading Head-to-Head History...**")
            res = await get_head_to_head(t1, t2)
            await query.message.edit_text(res, reply_markup=back_to_main(), parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await query.message.edit_text(
        f"⚠️ **Error processing request:** `{str(e)}`",
        reply_markup=back_to_main()
    )
