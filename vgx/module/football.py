import requests
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from vgx import app
from config import Config


# Get your free key from https://www.football-data.org/
#FOOTBALL_API_KEY = "" 


def scrape_todays_matches():
    """Fetches today's football matches from the API."""
    url = "https://api.football-data.org/v4/matches"
    headers = {
        "X-Auth-Token": Config.FOOTBALL_API_KEY
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        matches = data.get("matches", [])
        if not matches:
            return "❌ No major football matches are scheduled for today."
        
        # Build a beautifully formatted message
        msg = "🏆 **Today's Football Matches** 🏆\n\n"
        
        # Limit to the first 10 matches to avoid hitting Telegram's message length limit
        for match in matches[:10]:
            comp = match["competition"]["name"]
            home_team = match["homeTeam"]["name"]
            away_team = match["awayTeam"]["name"]
            status = match["status"]
            
            # If the match is finished, show the score
            if status in ["FINISHED", "IN_PLAY", "PAUSED"]:
                home_score = match["score"]["fullTime"]["home"]
                away_score = match["score"]["fullTime"]["away"]
                score_str = f"[{home_score} - {away_score}]"
            else:
                score_str = "[ vs ]"
                
            msg += f"🏅 **{comp}**\n"
            msg += f"⚽ {home_team} {score_str} {away_team}\n"
            msg += f"📌 Status: `{status}`\n"
            msg += "──────────────\n"
            
        return msg

    except Exception as e:
        return f"⚠️ Error fetching data: {e}"




@app.on_message(filters.command("matches"))
async def matches_cmd(client, message):
    # Send a waiting message since the API call might take a second
    processing_msg = await message.reply_text("⏳ Scraping latest football data...")
    
    # Fetch the data
    football_data = scrape_todays_matches()
    
    # Edit the waiting message with the actual data
    await processing_msg.edit_text(
        text=football_data,
        parse_mode=ParseMode.MARKDOWN
    )


from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from datetime import datetime, timedelta  # 👈 Add this import at the top of your file!

# ... (Keep your Client, filters, and configuration the same) ...

def fetch_matches(date_filter="TODAY", league_code=None):
    """Fetches upcoming fixtures and delayed live scores."""
    
    # 1. Calculate the exact YYYY-MM-DD format using datetime
    today = datetime.now()
    if date_filter == "YESTERDAY":
        target_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    elif date_filter == "TOMORROW":
        target_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        target_date = today.strftime("%Y-%m-%d")

    # 2. Set the correct API endpoints
    if league_code:
        url = f"https://api.football-data.org/v4/competitions/{league_code}/matches"
    else:
        url = "https://api.football-data.org/v4/matches"
        
    # 3. Use dateFrom and dateTo as required by the API
    params = {
        "dateFrom": target_date,
        "dateTo": target_date
    }
    
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 429:
            return "⚠️ **Rate Limit Exceeded!** Please wait a minute."
            
        # This will now pass successfully instead of throwing a 400 error!
        response.raise_for_status()
        data = response.json()
        matches = data.get("matches", [])
        
        if not matches:
            return f"❌ No matches found for your selected criteria ({target_date})."
        
        msg = f"🏆 **Football Fixtures & Scores ({target_date})** 🏆\n\n"
        
        for match in matches[:10]:
            comp = match["competition"]["name"]
            home_team = match["homeTeam"]["name"]
            away_team = match["awayTeam"]["name"]
            status = match["status"]
            
            if status in ["FINISHED", "IN_PLAY", "PAUSED"]:
                home_score = match["score"]["fullTime"]["home"]
                away_score = match["score"]["fullTime"]["away"]
                score_str = f"[{home_score} - {away_score}]"
            else:
                score_str = "[ vs ]"
                
            msg += f"🏅 **{comp}**\n⚽ {home_team} {score_str} {away_team}\n📌 Status: `{status}`\n──────────────\n"
        return msg
        
    except Exception as e:
        return f"⚠️ Error fetching data: {e}"



def fetch_standings(league_code="PL"):
    """Fetches the current League Table for a specific competition."""
    url = f"https://api.football-data.org/v4/competitions/{league_code}/standings"
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 429:
            return "⚠️ **Rate Limit Exceeded!** Please wait a minute."
            
        response.raise_for_status()
        data = response.json()
        standings = data.get("standings", [])
        
        if not standings:
            return "❌ Standings are not available for this league right now (e.g., Cup competitions)."
            
        table = standings[0].get("table", [])
        msg = f"📊 **League Table: {data['competition']['name']}**\n\n"
        
        msg += "`#  | Team       | Pts | GD`\n"
        msg += "`----------------------------`\n"
        
        for row in table[:15]:
            pos = str(row['position']).ljust(2)
            team = row['team']['shortName'][:10].ljust(10)
            pts = str(row['points']).ljust(3)
            gd = str(row['goalDifference']).ljust(3)
            
            msg += f"`{pos} | {team} | {pts} | {gd}`\n"
            
        return msg
    except Exception as e:
        return f"⚠️ Error fetching standings: {e}"


# --- KEYBOARDS ---
def get_main_menu():
    """Generates the interactive inline menu with ALL 12 free tier competitions."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 Plan Info", callback_data="info_free_tier"),
            InlineKeyboardButton("📊 View PL Table", callback_data="standings_PL")
        ],
        [
            InlineKeyboardButton("⏪ Yesterday", callback_data="date_YESTERDAY"),
            InlineKeyboardButton("📅 Today", callback_data="date_TODAY"),
            InlineKeyboardButton("⏩ Tomorrow", callback_data="date_TOMORROW")
        ],
        # The 12 Supported Free Tier Competitions
        [
            InlineKeyboardButton("🌍 World Cup", callback_data="league_WC"),
            InlineKeyboardButton("🇪🇺 Champions League", callback_data="league_CL")
        ],
        [
            InlineKeyboardButton("🇪🇺 Euro Champ", callback_data="league_EC"),
            InlineKeyboardButton("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", callback_data="league_PL")
        ],
        [
            InlineKeyboardButton("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship", callback_data="league_ELC"),
            InlineKeyboardButton("🇩🇪 Bundesliga", callback_data="league_BL1")
        ],
        [
            InlineKeyboardButton("🇪🇸 Primera Division", callback_data="league_PD"),
            InlineKeyboardButton("🇮🇹 Serie A", callback_data="league_SA")
        ],
        [
            InlineKeyboardButton("🇫🇷 Ligue 1", callback_data="league_FL1"),
            InlineKeyboardButton("🇵🇹 Primeira Liga", callback_data="league_PPL")
        ],
        [
            InlineKeyboardButton("🇳🇱 Eredivisie", callback_data="league_DED"),
            InlineKeyboardButton("🇧🇷 Brasileiro Série A", callback_data="league_BSA")
        ]
    ])


# --- HANDLERS ---
@app.on_message(filters.command("matche"))
async def starrkrrcmd(client, message):
    await message.reply_text(
        "👋 **Football Bot!**\n\n"
        "Check live scores, fixtures, and league tables from your supported competitions below:",
        reply_markup=get_main_menu()
    )

@app.on_callback_query(filters.regex(r"^(date|league|info|standings)_(.+)"))
async def handle_buttons(client, query):
    match = query.matches[0]
    prefix = match.group(1) 
    value = match.group(2)   
    
    await query.answer("Fetching data...")
    
    # 1. Handle Plan Info
    if prefix == "info":
        tier_text = (
            "🟢 **Current Tier: Free**\n"
            "• 🏆 `12 Competitions`\n"
            "• 🕒 Scores delayed\n"
            "• 📅 Fixtures & schedules\n"
            "• 📉 League Tables"
        )
        await query.message.edit_text(tier_text, reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)
        return

    # 2. Handle League Table (Standings)
    if prefix == "standings":
        table_text = fetch_standings(league_code=value)
        await query.message.edit_text(table_text, reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)
        return

    # 3. Handle Fixtures & Scores (Dates and Leagues)
    date_filter = "TODAY"
    league_code = None
    
    if prefix == "date":
        date_filter = value
    elif prefix == "league":
        league_code = value
        
    result_text = fetch_matches(date_filter=date_filter, league_code=league_code)
    await query.message.edit_text(result_text, reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)

