import httpx
from config import Config
from vgx.database.footballdb import get_cached_api, set_cached_api

HEADERS = {
    "x-apisports-key": Config.API_FOOTBALL_KEY,
    "x-apisports-host": Config.API_FOOTBALL_HOST
}

async def fetch_api(endpoint: str, params: dict = None, cache_ttl: int = 1800) -> dict:
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

# --- API METHODS ---

async def get_live_scores() -> str:
    data = await fetch_api("fixtures", params={"live": "all"}, cache_ttl=30)
    results = data.get("response", [])
    if not results:
        return "😴 **No live football matches ongoing right now.**"

    lines = ["🔴 **LIVE MATCHES UPDATES**\n"]
    for item in results[:15]:
        home = item['teams']['home']['name']
        away = item['teams']['away']['name']
        gh = item['goals']['home'] if item['goals']['home'] is not None else 0
        ga = item['goals']['away'] if item['goals']['away'] is not None else 0
        m = item['fixture']['status']['elapsed'] or "0"
        league = item['league']['name']
        lines.append(f"• **[{league}]**\n  {home} `{gh}` - `{ga}` {away} (`{m}'`)")
    return "\n\n".join(lines)

async def get_standings(league_id: int) -> str:
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

async def get_top_scorers(league_id: int) -> str:
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

async def get_match_prediction(fixture_id: int) -> str:
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

async def get_lineups(fixture_id: int) -> str:
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

async def get_injuries(fixture_id: int) -> str:
    data = await fetch_api("injuries", params={"fixture": fixture_id}, cache_ttl=14400)
    injuries = data.get("response", [])
    if not injuries:
        return "✅ **No major injuries or absences reported for this match.**"

    msg = "🏥 **Injury & Absence Report**\n\n"
    for item in injuries:
        player = item["player"]["name"]
        team = item["team"]["name"]
        reason = item["player"]["reason"]
        msg += f"• **{player}** ({team})\n  ⚠️ `{reason}`\n"
    return msg

async def get_head_to_head(team1_id: int, team2_id: int) -> str:
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
