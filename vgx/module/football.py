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
