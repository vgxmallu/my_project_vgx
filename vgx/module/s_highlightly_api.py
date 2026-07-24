import httpx
from config import Config
from vgx.database.s_highlights_db import get_cached_api, set_cached_api

HEADERS = {"Authorization": f"Bearer {Config.HIGHLIGHTLY_API_KEY}"}

async def fetch_hl_api(endpoint: str, params: dict = None, ttl: int = 300) -> dict:
    cache_key = f"hl_{endpoint}_{str(params)}"
    cached = await get_cached_api(cache_key)
    if cached: return cached

    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(f"{config.HIGHLIGHTLY_BASE_URL}/{endpoint}", headers=HEADERS, params=params)
            if res.status_code == 200:
                data = res.json()
                await set_cached_api(cache_key, data, ttl)
                return data
        except Exception: pass
    return {}

async def format_live_scores(sport: str) -> str:
    data = await fetch_hl_api(f"{sport}/live", ttl=60)
    matches = data.get("data", [])
    if not matches: return f"😴 **No live {sport} matches right now.**"

    text = f"🔴 **LIVE {sport.upper()} MATCHES**\n\n"
    for m in matches[:10]:
        h, a = m['teams']['home'], m['teams']['away']
        # Highlightly provides logos and scores in a unified schema
        text += f"[{h['name']}]({h['logo']}) `{m['scores']['home']}` - `{m['scores']['away']}` [{a['name']}]({a['logo']}) "
        text += f"(`{m['status']['clock']}`)\n"
    return text

async def format_highlights(sport: str) -> str:
    data = await fetch_hl_api(f"{sport}/highlights", ttl=600)
    vids = data.get("data", [])
    if not vids: return "⚠️ No recent highlights found."
    
    text = f"🎬 **{sport.upper()} HIGHLIGHTS**\n\n"
    for v in vids[:5]:
        text += f"📹 **{v['title']}**\n[Watch Video]({v['url']}) | *{v['category']}*\n\n"
    return text

async def format_h2h(sport: str, team1_id: int, team2_id: int) -> str:
    data = await fetch_hl_api(f"{sport}/h2h", params={"team1": team1_id, "team2": team2_id}, ttl=3600)
    matches = data.get("data", [])
    text = "⚔️ **HEAD-TO-HEAD (Last 5)**\n\n"
    for m in matches[:5]:
        text += f"📅 {m['date']} | {m['teams']['home']['name']} `{m['scores']['home']}-{m['scores']['away']}` {m['teams']['away']['name']}\n"
    return text
