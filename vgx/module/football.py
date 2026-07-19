import requests
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from vgx import app


# Get your free key from https://www.football-data.org/
FOOTBALL_API_KEY = "2d92105f0d534281b711e8ea189cd8e4" 


def scrape_todays_matches():
    """Fetches today's football matches from the API."""
    url = "https://api.football-data.org/v4/matches"
    headers = {
        "X-Auth-Token": FOOTBALL_API_KEY
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


import requests
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

# --- CONFIGURATION ---
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
API_ID = "YOUR_API_ID"        
API_HASH = "YOUR_API_HASH"    
FOOTBALL_API_KEY = "YOUR_FOOTBALL_DATA_API_KEY" 

app = Client("football_advanced_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def fetch_matches(date_filter="TODAY", league_code=None):
    """Fetches football matches with date and league filters."""
    
    # 1. Determine which endpoint to hit
    if league_code:
        # Fetch for a specific competition using its code
        url = f"https://api.football-data.org/v4/competitions/{league_code}/matches"
    else:
        # Fetch all general matches
        url = "https://api.football-data.org/v4/matches"
        
    # 2. Add our filters to the request parameters
    params = {"date": date_filter}
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        
        # 3. Handle API quota limits safely
        if response.status_code == 429:
            return "⚠️ **Rate Limit Exceeded!** You have made too many requests to the API. Please wait a minute."
            
        response.raise_for_status()
        data = response.json()
        
        matches = data.get("matches", [])
        if not matches:
            return f"❌ No matches found for your selected criteria ({date_filter})."
        
        # 4. Build the beautifully formatted message
        msg = f"🏆 **Football Matches ({date_filter})** 🏆\n\n"
        
        for match in matches[:10]:
            comp = match["competition"]["name"]
            home_team = match["homeTeam"]["name"]
            away_team = match["awayTeam"]["name"]
            status = match["status"]
            
            # Score handling based on match status
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

# --- KEYBOARDS ---
def get_main_menu():
    """Generates the interactive inline button menu."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏪ Yesterday", callback_data="date_YESTERDAY"),
            InlineKeyboardButton("📅 Today", callback_data="date_TODAY"),
            InlineKeyboardButton("⏩ Tomorrow", callback_data="date_TOMORROW")
        ],
        [
            InlineKeyboardButton("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", callback_data="league_PL"),
            InlineKeyboardButton("🇩🇪 Bundesliga", callback_data="league_BL1")
        ],
        [
            InlineKeyboardButton("🇪🇸 La Liga", callback_data="league_PD"),
            InlineKeyboardButton("🇮🇹 Serie A", callback_data="league_SA")
        ]
    ])

# --- HANDLERS ---

@app.on_message(filters.command("matches2"))
async def sthh_cmd(client, message):
    await message.reply_text(
        "**Advanced Football Bot!**\n\n"
        "Use the buttons below to filter matches by date or by specific top leagues:",
        reply_markup=get_main_menu()
    )

# This regex captures either 'date' or 'league' in group 1, and the value in group 2
@app.on_callback_query(filters.regex(r"^(date|league)_(.+)"))
async def handle_buttons(client, query):
    """Listens for filtered callback data and updates the message using regex matches."""
    
    # 1. Send a quick loading alert so the button doesn't feel frozen
    await query.answer("Fetching data from the API...")
    
    # 2. Extract variables natively from the regex groups
    match = query.matches[0]
    prefix = match.group(1)  # Contains either 'date' or 'league'
    value = match.group(2)   # Contains values like 'TODAY', 'PL', 'SA', etc.
    
    # 3. Set up default parameters for the API fetch function
    date_filter = "TODAY"
    league_code = None
    
    if prefix == "date":
        date_filter = value
    elif prefix == "league":
        league_code = value
        
    # 4. Fetch the formatted text from the API
    result_text = fetch_matches(date_filter=date_filter, league_code=league_code)
    
    # 5. Edit the original message to show the new data while maintaining the menu
    await query.message.edit_text(
        text=result_text,
        reply_markup=get_main_menu(),
        parse_mode=ParseMode.MARKDOWN
    )
