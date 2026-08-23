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
  
