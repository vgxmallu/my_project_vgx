import httpx
from config import Config
from vgx.database.fdb import get_cached_api, set_cached_api

HEADERS = {"X-Auth-Token": Config.FOOTBALL_API_KEY}

async def fetch_football_data(endpoint: str, params: dict = None, ttl: int = 300) -> dict:
    """Fetches data with built-in MongoDB TTL caching to comply with 10 req/min rate limit."""
    cache_key = f"fd_{endpoint}_{str(params)}"
    cached = await get_cached_api(cache_key)
    if cached:
        return cached

    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(
                f"{Config.FOOTBALL_DATA_BASE_URL}/{endpoint}",
                headers=HEADERS,
                params=params,
                timeout=10.0
            )
            if res.status_code == 200:
                data = res.json()
                await set_cached_api(cache_key, data, ttl)
                return data
        except Exception:
            pass
    return {}

async def format_standings(competition_code: str) -> str:
    data = await fetch_football_data(f"competitions/{competition_code}/standings", ttl=600)
    if not data or "standings" not in data:
        return f"⚠️ Could not load standings for `{competition_code}`."

    comp_name = data.get("competition", {}).get("name", competition_code)
    standings_table = data["standings"][0].get("table", [])
    
    text = f"🏆 **{comp_name} Standings**\n\n"
    text += "`Pos  Team               P   GD  Pts`\n"
    text += "`-----------------------------------`\n"
    
    for row in standings_table[:12]:
        pos = str(row['position']).ljust(3)
        name = row['team']['tla'] if row['team'].get('tla') else row['team']['shortName'][:10]
        name = name.ljust(17)
        p = str(row['playedGames']).rjust(2)
        gd = str(row['goalDifference']).rjust(4)
        pts = str(row['points']).rjust(3)
        text += f"`{pos} {name} {p}  {gd}  {pts}`\n"
        
    return text

async def format_fixtures(competition_code: str) -> str:
    data = await fetch_football_data(f"competitions/{competition_code}/matches", params={"status": "SCHEDULED"}, ttl=300)
    matches = data.get("matches", [])
    if not matches:
        return f"📅 **No upcoming matches scheduled for {competition_code}.**"

    comp_name = Config.COMPETITIONS.get(competition_code, competition_code)
    text = f"📅 **Upcoming Fixtures — {comp_name}**\n\n"
    
    for m in matches[:8]:
        date_str = m['utcDate'][:10]
        home = m['homeTeam']['name']
        away = m['awayTeam']['name']
        text += f"• `{date_str}`: **{home}** vs **{away}**\n"
        
    return text

async def format_recent_results_with_spoilers(competition_code: str) -> str:
    """Uses Telegram spoiler tags to protect scores."""
    data = await fetch_football_data(f"competitions/{competition_code}/matches", params={"status": "FINISHED"}, ttl=300)
    matches = data.get("matches", [])
    if not matches:
        return f"⚽ No recent results for {competition_code}."

    text = f"⚽ **Recent Results (Click score to reveal)**\n\n"
    for m in matches[-6:]:
        home = m['homeTeam']['name']
        away = m['awayTeam']['name']
        h_score = m['score']['fullTime']['home']
        a_score = m['score']['fullTime']['away']
        
        # Wrapped in Telegram spoiler syntax
        text += f"• {home} vs {away} — ||{h_score} - {a_score}||\n"
        
    return text


async def format_scorers(competition_code: str) -> str:
    """Fetches the top scorers (Golden Boot race) for a specific competition."""
    data = await fetch_football_data(f"competitions/{competition_code}/scorers", ttl=3600)
    scorers = data.get("scorers", [])
    if not scorers:
        return f"⚽ No scorer data available for `{competition_code}`."

    comp_name = data.get("competition", {}).get("name", competition_code)
    text = f"🎯 **Top Scorers — {comp_name}**\n\n"
    text += "`Pos  Player             Team         Gls`\n"
    text += "`----------------------------------------`\n"
    
    for idx, s in enumerate(scorers[:10], start=1):
        pos = str(idx).ljust(3)
        player = s['player']['name'][:16].ljust(18)
        team = s['team']['shortName'][:10].ljust(11)
        goals = str(s.get('goals', 0)).rjust(3)
        text += f"`{pos} {player} {team} {goals}`\n"
        
    return text

async def format_today_matches() -> str:
    """Uses the v4 'TODAY' shortcut filter to get all matches across covered leagues."""
    data = await fetch_football_data("matches", params={"date": "TODAY"}, ttl=300)
    matches = data.get("matches", [])
    if not matches:
        return "⚽ No matches scheduled for today across your covered competitions."

    text = "🗓 **Today's Global Matches**\n\n"
    for m in matches[:15]:  # Limit to 15 to avoid Telegram message length limits
        comp = m['competition']['code']
        home = m['homeTeam']['shortName']
        away = m['awayTeam']['shortName']
        status = m['status']
        
        if status == "IN_PLAY":
            score = f"🔴 {m['score']['fullTime']['home']} - {m['score']['fullTime']['away']}"
        elif status == "FINISHED":
            score = f"✅ {m['score']['fullTime']['home']} - {m['score']['fullTime']['away']}"
        else:
            # Note: UTC time. Your server/users can adjust to IST or local timezone here.
            score = "🕒 " + m['utcDate'][11:16] + " UTC" 
            
        text += f"**[{comp}]** {home} vs {away} | {score}\n"
        
    return text

async def format_squad(team_id: int) -> str:
    """Fetches the active roster for a specific team."""
    data = await fetch_football_data(f"teams/{team_id}", ttl=86400) # Cache for 24h
    squad = data.get("squad", [])
    if not squad:
        return "⚠️ Squad data not available. Ensure you used a valid Team ID."

    team_name = data.get("name", "Team")
    coach = data.get("coach", {}).get("name", "Unknown")
    
    text = f"🛡️ **{team_name} — Current Squad**\n"
    text += f"👔 **Coach:** {coach}\n\n"
    text += "`Pos  Name                  Nationality`\n"
    text += "`--------------------------------------`\n"
    
    for p in squad:
        pos = (p.get('position') or 'N/A')[:3].upper().ljust(4)
        name = p.get('name', 'Unknown')[:20].ljust(21)
        nat = p.get('nationality', 'Unknown')[:10]
        text += f"`{pos} {name} {nat}`\n"
        
    return text[:4000] 
