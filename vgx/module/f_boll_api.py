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
