import aiohttp
from config import Config

class PubgAPI:
    def __init__(self, platform: str = "steam"):
        self.api_key = Config.PUBG_API_KEY
        self.platform = platform
        self.base_url = f"https://api.pubg.com/shards/{self.platform}"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/vnd.api+json"
        }

    async def _fetch(self, url: str) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    return await response.json()
                return {}

    async def get_player_id(self, player_name: str) -> str:
        """Translates a player name into a PUBG account ID."""
        url = f"{self.base_url}/players?filter[playerNames]={player_name}"
        data = await self._fetch(url)
        try:
            return data["data"][0]["id"]
        except (KeyError, IndexError):
            return None

    async def get_lifetime_stats(self, account_id: str) -> dict:
        """Fetches lifetime statistics for all game modes."""
        url = f"{self.base_url}/players/{account_id}/seasons/lifetime"
        data = await self._fetch(url)
        return data.get("data", {}).get("attributes", {}).get("gameModeStats", {})

    async def get_survival_mastery(self, account_id: str) -> dict:
        """Fetches level, total matches, and survival stats."""
        url = f"{self.base_url}/players/{account_id}/survival_mastery"
        data = await self._fetch(url)
        return data.get("data", {}).get("attributes", {})

    async def get_player_matches(self, player_name: str) -> tuple[str, list]:
        """Fetches a player's account ID and their list of recent match IDs."""
        url = f"{self.base_url}/players?filter[playerNames]={player_name}"
        data = await self._fetch(url)
        try:
            player_data = data["data"][0]
            account_id = player_data["id"]
            matches = [m["id"] for m in player_data["relationships"]["matches"]["data"]]
            return account_id, matches
        except (KeyError, IndexError):
            return None, []

    async def get_match_details(self, match_id: str, account_id: str) -> dict:
        """Fetches detailed stats for a specific match and extracts the target player's stats."""
        url = f"{self.base_url}/matches/{match_id}"
        data = await self._fetch(url)
        if not data:
            return {}

        match_attr = data.get("data", {}).get("attributes", {})
        included = data.get("included", [])

        # Locate the participant object matching our account ID
        player_stats = {}
        for item in included:
            if item.get("type") == "participant":
                attrs = item.get("attributes", {})
                stats = attrs.get("stats", {})
                if stats.get("playerId") == account_id:
                    player_stats = stats
                    break

        return {
            "map": match_attr.get("mapName", "Unknown"),
            "mode": match_attr.get("gameMode", "Unknown"),
            "duration": match_attr.get("duration", 0),
            "created_at": match_attr.get("createdAt", ""),
            "stats": player_stats
        }

    async def get_weapon_mastery(self, account_id: str) -> dict:
        """Fetches weapon levels, total kills, and headshots."""
        url = f"{self.base_url}/players/{account_id}/weapon_mastery"
        data = await self._fetch(url)
        return data.get("data", {}).get("attributes", {}).get("weaponSummaries", {})

    async def get_current_season(self) -> str:
        """Fetches the active season ID (e.g., 'division.bro.official.pc-2018-29')."""
        url = f"{self.base_url}/seasons"
        data = await self._fetch(url)
        
        for season in data.get("data", []):
            if season.get("attributes", {}).get("isCurrentSeason"):
                return season.get("id")
        return None

    async def get_ranked_stats(self, account_id: str, season_id: str) -> dict:
        """Fetches competitive stats and tier data for a specific season."""
        url = f"{self.base_url}/players/{account_id}/seasons/{season_id}/ranked"
        data = await self._fetch(url)
        return data.get("data", {}).get("attributes", {}).get("rankedGameModeStats", {})
        
pubg = PubgAPI()






def format_stats(player_name: str, mode: str, stats: dict) -> str:
    if not stats:
        return f"❌ No data available for **{player_name}** in **{mode.upper()}**."

    kills = stats.get('kills', 0)
    deaths = stats.get('losses', 0)
    kd_ratio = round(kills / deaths, 2) if deaths > 0 else kills

    text = (
        f"📊 **PUBG Stats: {player_name}**\n"
        f"🎮 **Mode:** {mode.replace('-', ' ').upper()}\n\n"
        f"🏆 **Wins:** {stats.get('wins', 0)}\n"
        f"💀 **Kills:** {kills}\n"
        f"📉 **K/D Ratio:** {kd_ratio}\n"
        f"🎯 **Headshot Kills:** {stats.get('headshotKills', 0)}\n"
        f"📏 **Longest Kill:** {stats.get('longestKill', 0):.2f}m\n"
        f"🔥 **Max Kills/Round:** {stats.get('roundMostKills', 0)}\n"
        f"🚗 **Road Kills:** {stats.get('roadKills', 0)}\n"
        f"🏅 **Top 10s:** {stats.get('top10s', 0)}"
    )
    return text

def format_survival(player_name: str, stats: dict) -> str:
    if not stats:
        return "❌ Survival data not found."
        
    return (
        f"🎒 **Survival Mastery: {player_name}**\n\n"
        f"🌟 **Level:** {stats.get('level', 1)}\n"
        f"🎮 **Matches Played:** {stats.get('totalMatchesPlayed', 0)}"
    )

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def stats_kb(account_id: str, current_mode: str) -> InlineKeyboardMarkup:
    # Remove 'account.' to save bytes in callback_data
    short_id = account_id.replace("account.", "")
    
    modes = [
        ("solo", "Solo"), ("duo", "Duo"), ("squad", "Squad"),
        ("solo-fpp", "Solo FPP"), ("duo-fpp", "Duo FPP"), ("squad-fpp", "Squad FPP")
    ]
    
    buttons = []
    row = []
    
    for mode_key, mode_label in modes:
        btn_text = f"✅ {mode_label}" if current_mode == mode_key else mode_label
        row.append(InlineKeyboardButton(btn_text, callback_data=f"pubg|{mode_key}|{short_id}"))
        
        if len(row) == 3:
            buttons.append(row)
            row = []
            
    if row:
        buttons.append(row)
        
    return InlineKeyboardMarkup(buttons)


#====================================================

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
import re
import aiohttp

@Client.on_message(filters.command("pubgstats"))
async def cmd_pubgstats(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/stats <PlayerName>`")
    
    player_name = message.command[1]
    msg = await message.reply_text(f"🔎 Searching PUBG servers for `{player_name}`...")
    
    account_id = await pubg.get_player_id(player_name)
    if not account_id:
        return await msg.edit_text("❌ **Player not found.** (Check spelling or platform).")

    stats_data = await pubg.get_lifetime_stats(account_id)
    if not stats_data:
        return await msg.edit_text("❌ **No lifetime stats found.**")

    # Default to Squad FPP when they first run the command
    default_mode = "squad-fpp"
    text = format_stats(player_name, default_mode, stats_data.get(default_mode, {}))
    kb = stats_kb(account_id, default_mode)
    
    await msg.edit_text(text, reply_markup=kb)

@Client.on_callback_query(filters.regex(r"^pubg\|(.+)\|(.+)$"))
async def callback_stats(client: Client, query: CallbackQuery):
    mode, short_id = query.matches[0].groups()
    account_id = f"account.{short_id}"
    
    await query.answer()
    
    # Extract player name from the existing message text
    player_name_match = re.search(r"PUBG Stats: (.+)", query.message.text)
    player_name = player_name_match.group(1) if player_name_match else "Player"
    
    stats_data = await pubg.get_lifetime_stats(account_id)
    text = format_stats(player_name, mode, stats_data.get(mode, {}))
    kb = stats_kb(account_id, mode)
    
    try:
        await query.edit_message_text(text, reply_markup=kb)
    except Exception:
        pass # Ignore if the user clicks the tab they are already on

@Client.on_message(filters.command("pg_survival"))
async def cmd_suggrvival(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/survival <PlayerName>`")
    
    player_name = message.command[1]
    msg = await message.reply_text(f"🔎 Checking survival mastery for `{player_name}`...")
    
    account_id = await pubg.get_player_id(player_name)
    if not account_id:
        return await msg.edit_text("❌ **Player not found.**")

    survival_data = await pubg.get_survival_mastery(account_id)
    text = format_survival(player_name, survival_data)
    
    await msg.edit_text(text)
  

@Client.on_message(filters.command("pglastmatch"))
async def cmd_lashtmatch(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/lastmatch <PlayerName>`")

    player_name = message.command[1]
    msg = await message.reply_text(f"🔎 Fetching latest match for `{player_name}`...")

    account_id, matches = await pubg.get_player_matches(player_name)
    if not account_id or not matches:
        return await msg.edit_text("❌ **No recent matches found for this player.**")

    latest_match_id = matches[0]
    match_data = await pubg.get_match_details(latest_match_id, account_id)
    stats = match_data.get("stats", {})

    if not stats:
        return await msg.edit_text("❌ **Could not parse player stats for the match.**")

    duration_min = round(match_data.get("duration", 0) / 60, 1)
    time_survived_min = round(stats.get("timeSurvived", 0) / 60, 1)

    text = (
        f"🎮 **Last Match Summary: {player_name}**\n\n"
        f"🗺️ **Map:** {match_data.get('map')}\n"
        f"🎯 **Game Mode:** {match_data.get('mode').upper()}\n"
        f"🏆 **Placement:** #{stats.get('winPlace', 'N/A')}\n\n"
        f"💀 **Kills:** {stats.get('kills', 0)}\n"
        f"💥 **Damage Dealt:** {round(stats.get('damageDealt', 0), 1)}\n"
        f"🎯 **Assists:** {stats.get('assists', 0)}\n"
        f"🩺 **DBNOs (Knocks):** {stats.get('DBNOs', 0)}\n"
        f"💉 **Heals Used:** {stats.get('heals', 0)}\n"
        f"⏱️ **Survived:** {time_survived_min} / {duration_min} mins"
    )

    await msg.edit_text(text)


@Client.on_message(filters.command("pgweapons"))
async def cmd_whpeapons(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/weapons <PlayerName>`")

    player_name = message.command[1]
    msg = await message.reply_text(f"🔎 Fetching weapon mastery for `{player_name}`...")

    account_id = await pubg.get_player_id(player_name)
    if not account_id:
        return await msg.edit_text("❌ **Player not found.**")

    weapons_data = await pubg.get_weapon_mastery(account_id)
    if not weapons_data:
        return await msg.edit_text("❌ **No weapon mastery data found.**")

    # Sort weapons by highest level
    sorted_weapons = sorted(
        weapons_data.items(),
        key=lambda x: x[1].get("LevelCurrent", 0),
        reverse=True
    )

    text = f"🔫 **Top Weapon Mastery: {player_name}**\n\n"
    for weapon_id, stats in sorted_weapons[:5]: # Top 5 weapons
        clean_name = weapon_id.replace("Item_Weapon_", "").replace("_C", "")
        level = stats.get("LevelCurrent", 1)
        stats_official = stats.get("StatsOfficial", {})
        kills = stats_official.get("Kills", {}).get("Value", 0)
        headshots = stats_official.get("HeadShots", {}).get("Value", 0)

        text += f"▪️ **{clean_name}** (Lvl {level})\n"
        text += f"   ↳ Kills: `{kills}` | Headshots: `{headshots}`\n\n"

    await msg.edit_text(text)

@Client.on_message(filters.command("ranked"))
async def cmd_ranked(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/ranked <PlayerName>`")

    player_name = message.command[1]
    msg = await message.reply_text(f"🔎 Fetching ranked data for `{player_name}`...")

    account_id = await pubg.get_player_id(player_name)
    if not account_id:
        return await msg.edit_text("❌ **Player not found.**")

    season_id = await pubg.get_current_season()
    if not season_id:
        return await msg.edit_text("❌ **Could not determine the current active season.**")

    ranked_data = await pubg.get_ranked_stats(account_id, season_id)
    
    # Most competitive players play Squad FPP
    squad_fpp = ranked_data.get("squad-fpp", {})
    
    if not squad_fpp or squad_fpp.get("roundsPlayed", 0) == 0:
        return await msg.edit_text(f"❌ **{player_name}** hasn't played Ranked Squad FPP this season.")

    current_tier = squad_fpp.get("currentTier", {})
    tier_name = current_tier.get("tier", "Unranked")
    sub_tier = current_tier.get("subTier", "")
    
    kills = squad_fpp.get("kills", 0)
    deaths = squad_fpp.get("deaths", 0)
    kd_ratio = round(kills / deaths, 2) if deaths > 0 else kills

    text = (
        f"🎖️ **Ranked Profile: {player_name}**\n\n"
        f"🏆 **Tier:** {tier_name} {sub_tier}\n"
        f"📈 **Rank Points (RP):** {current_tier.get('currentRankPoint', 0)}\n\n"
        f"⚔️ **Matches Played:** {squad_fpp.get('roundsPlayed', 0)}\n"
        f"🍗 **Wins:** {squad_fpp.get('wins', 0)}\n"
        f"💀 **K/D Ratio:** {kd_ratio}\n"
        f"🎯 **Average Damage:** {round(squad_fpp.get('damageDealt', 0) / squad_fpp.get('roundsPlayed', 1), 1)}"
    )

    await msg.edit_text(text)

@Client.on_message(filters.command("airdrop"))
async def cmd_airdrop(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/airdrop <PlayerName>`")

    player_name = message.command[1]
    msg = await message.reply_text(f"🔎 Scanning telemetry for airdrops in `{player_name}`'s last match...")

    account_id, matches = await pubg.get_player_matches(player_name)
    if not account_id or not matches:
        return await msg.edit_text("❌ **No recent matches found.**")

    # 1. Get the telemetry URL for the last match
    match_data = await pubg.get_match_details(matches[0], account_id)
    # Note: You will need to update `get_match_details` to return the telemetry URL.
    # The URL is stored in the included array where type == "asset".
    
    # For the sake of this code, we assume you have the telemetry URL
    telemetry_url = match_data.get("telemetry_url") 
    if not telemetry_url:
        return await msg.edit_text("❌ **Could not locate the telemetry file for this match.**")

    # 2. Fetch and parse the telemetry file
    loot_events = []
    async with aiohttp.ClientSession() as session:
        async with session.get(telemetry_url, headers={"Accept-Encoding": "gzip"}) as response:
            telemetry_data = await response.json()
            
            for event in telemetry_data:
                if event.get("_T") == "LogItemPickupFromCarepackage":
                    looter_name = event.get("character", {}).get("name", "Unknown")
                    raw_item = event.get("item", {}).get("itemId", "Unknown")
                    clean_item = raw_item.replace("Item_", "").replace("_C", "").replace("Weapon_", "")
                    
                    loot_events.append(f"📦 **{looter_name}** looted `{clean_item}`")

    if not loot_events:
        return await msg.edit_text("❌ No airdrops were looted in that match, or telemetry is empty.")

    # 3. Format and send the results
    # Limit to the last 15 items so we don't hit Telegram's message length limits
    text = f"🪂 **Airdrop Loot History** (Last Match)\n\n" + "\n".join(loot_events[-15:])
    await msg.edit_text(text)
