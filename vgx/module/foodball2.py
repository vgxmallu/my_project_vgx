import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from config import Config
from vgx import app

# API-Football Credentials
BASE_URL = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": Config.API_FOOTBALL_KEY
}


# --- KEYBOARDS ---
def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔴 Live Scores", callback_data="apifootball_live"),
            InlineKeyboardButton("📊 Standings (EPL)", callback_data="apifootball_standings_39")
        ],
        [
            InlineKeyboardButton("📅 Today's Fixtures", callback_data="apifootball_today"),
            InlineKeyboardButton("🏆 Top Scorers (EPL)", callback_data="apifootball_topscorers_39")
        ]
    ])

def back_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="apifootball_main")]
    ])

# --- API HELPER FUNCTION ---
async def fetch_api_data(endpoint: str, params: dict = None) -> dict:
    """Helper function to perform async requests to API-Football."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=params)
        if response.status_code == 200:
            return response.json()
        return {}

# --- BOT HANDLERS ---
@app.on_message(filters.command("football2"))
async def staddkkdrt_cmd(client: Client, message: Message):
    if not message.from_user:
        return

    await message.reply_text(
        "⚽ **API-Football Live Engine**\n\n"
        "Choose an option below to fetch real-time football data:",
        reply_markup=main_menu(),
        parse_mode=ParseMode.MARKDOWN
    )

# 🎯 REGEX ROUTER FOR API-FOOTBALL ACTIONS
@app.on_callback_query(filters.regex(r"^apifootball_(.+)"))
async def callbfsoack_router(client: Client, query: CallbackQuery):
    await query.answer()
    
    match = query.matches[0].group(1)

    # 1. Main Navigation
    if match == "main":
        await query.message.edit_text(
            "⚽ **API-Football Live Engine**\n\n"
            "Choose an option below to fetch real-time football data:",
            reply_markup=main_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # 2. Live Scores
    if match == "live":
        await query.message.edit_text("⏳ **Fetching live matches...**", parse_mode=ParseMode.MARKDOWN)
        data = await fetch_api_data("fixtures", params={"live": "all"})
        
        results = data.get("response", [])
        if not results:
            await query.message.edit_text("😴 **No live matches ongoing right now.**", reply_markup=back_button())
            return

        lines = ["🔴 **CURRENT LIVE MATCHES**\n"]
        for item in results[:10]:  # Limit to 10 matches
            home = item['teams']['home']['name']
            away = item['teams']['away']['name']
            goals_home = item['goals']['home']
            goals_away = item['goals']['away']
            minute = item['fixture']['status']['elapsed']
            lines.append(f"• **{home}** {goals_home} - {goals_away} **{away}** ({minute}')")

        await query.message.edit_text("\n".join(lines), reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
        return

    # 3. League Standings (e.g., League ID 39 = Premier League)
    if match.startswith("standings_"):
        league_id = match.split("_")[1]
        await query.message.edit_text("⏳ **Fetching Standings...**", parse_mode=ParseMode.MARKDOWN)
        
        # Season 2025/2026
        data = await fetch_api_data("standings", params={"league": league_id, "season": "2025"})
        
        try:
            standings_list = data["response"][0]["league"]["standings"][0]
            league_name = data["response"][0]["league"]["name"]
            
            output = f"🏆 **{league_name} Standings (2025/26)**\n\n"
            output += "`Pos | Team             | Pts | GD`\n"
            output += "`---------------------------------`\n"

            for team in standings_list[:10]: # Top 10
                rank = str(team['rank']).rjust(2)
                name = team['team']['name'][:15].ljust(15)
                pts = str(team['points']).rjust(3)
                gd = str(team['goalsDiff']).rjust(3)
                output += f"`{rank} | {name} | {pts} | {gd}`\n"

            await query.message.edit_text(output, reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
        except (KeyError, IndexError):
            await query.message.edit_text("⚠️ Failed to load standings or invalid season data.", reply_markup=back_button())
        return

    # 4. Top Scorers
    if match.startswith("topscorers_"):
        league_id = match.split("_")[1]
        await query.message.edit_text("⏳ **Fetching Top Scorers...**", parse_mode=ParseMode.MARKDOWN)
        
        data = await fetch_api_data("players/topscorers", params={"league": league_id, "season": "2025"})
        results = data.get("response", [])
        
        if not results:
            await query.message.edit_text("⚠️ Top scorers data unavailable.", reply_markup=back_button())
            return

        lines = ["🎯 **TOP SCORERS**\n"]
        for idx, item in enumerate(results[:10], start=1):
            player = item['player']['name']
            team = item['statistics'][0]['team']['name']
            goals = item['statistics'][0]['goals']['total']
            lines.append(f"{idx}. **{player}** ({team}) — ⚽ `{goals}` Goals")

        await query.message.edit_text("\n".join(lines), reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)
        return
