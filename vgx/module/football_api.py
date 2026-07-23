import httpx
from config import Config
from vgx.database.footballdb import get_cached_api, set_cached_api

HEADERS = {
    "x-apisports-key": Config.API_FOOTBALL_KEY,
    "x-apisports-host": Config.API_FOOTBALL_HOST
}

async def fetch_api(endpoint: str, params: dict = None, ttl: int = 1800) -> dict:
    param_str = "_".join([f"{k}:{v}" for k, v in sorted(params.items())]) if params else "none"
    cache_key = f"{endpoint}_{param_str}"

    cached = await get_cached_api(cache_key)
    if cached: return cached

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{config.BASE_URL}/{endpoint}", headers=HEADERS, params=params)
            if response.status_code == 200:
                data = response.json()
                if data.get("response"):
                    await set_cached_api(cache_key, data, ttl_seconds=ttl)
                return data
        except Exception: pass
    return {}

async def get_live_scores() -> str:
    data = await fetch_api("fixtures", params={"live": "all"}, ttl=30)
    results = data.get("response", [])
    if not results: return "😴 **No live matches at the moment.**"

    lines = ["🔴 **LIVE MATCHES**\n"]
    for item in results[:15]:
        h, a = item['teams']['home']['name'], item['teams']['away']['name']
        gh, ga = item['goals']['home'] or 0, item['goals']['away'] or 0
        m = item['fixture']['status']['elapsed'] or "0"
        lines.append(f"• {h} `{gh}` - `{ga}` {a} (`{m}'`)")
    return "\n".join(lines)

async def get_standings(league_id: int, season: int = 2023) -> str:
    data = await fetch_api("standings", params={"league": league_id, "season": season}, ttl=3600)
    try:
        table = data["response"][0]["league"]["standings"][0]
        msg = f"🏆 **Standings**\n\n`Pos | Team         | Pts`\n`--------------------------`\n"
        for t in table[:10]:
            msg += f"`{str(t['rank']).rjust(2)}  | {t['team']['name'][:12].ljust(12)} | {str(t['points']).rjust(3)}`\n"
        return msg
    except Exception: return "⚠️ Standings unavailable."
