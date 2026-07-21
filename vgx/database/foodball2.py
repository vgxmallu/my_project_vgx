#============================================

import asyncio
import soccerdata as sd

def _fetch_fbref_sync(league_code: str, stat_type: str) -> str:
    """
    Synchronous function executing soccerdata scraping and Pandas operations.
    """
    try:
        fbref = sd.FBref(leagues=league_code, seasons="2324")
        
        # Scrape team stats based on selected button mode
        if stat_type == "shooting":
            df = fbref.read_team_season_stats(stat_type="shooting").reset_index()
            msg = f"📊 **FBref Shooting Stats: {league_code}**\n\n"
            msg += "`Team       | Sh  | SoT | Gls `\n`----------------------------`\n"
            
            for _, row in df.head(8).iterrows():
                team = str(row['team'])[:10].ljust(10)
                sh = str(row[('shooting', 'sh')]).ljust(3)
                sot = str(row[('shooting', 'sot')]).ljust(3)
                gls = str(row[('shooting', 'gls')]).ljust(3)
                msg += f"`{team} | {sh} | {sot} | {gls}`\n"
                
        else:
            df = fbref.read_team_season_stats(stat_type="standard").reset_index()
            msg = f"📊 **FBref Standard Stats: {league_code}**\n\n"
            msg += "`Team       | Pl  | Age | Poss `\n`----------------------------`\n"
            
            for _, row in df.head(8).iterrows():
                team = str(row['team'])[:10].ljust(10)
                players = str(row[('standard', 'players_used')]).ljust(2)
                age = str(row[('standard', 'age')]).ljust(3)
                poss = str(row[('standard', 'possession')]).ljust(4)
                msg += f"`{team} | {players} | {age} | {poss}%`\n"
                
        return msg
        
    except Exception as e:
        return f"⚠️ Scraping Error: {str(e)}"

async def get_fbref_stats(league_code: str, stat_type: str = "standard") -> str:
    """
    Non-blocking wrapper that runs soccerdata inside a dedicated worker thread.
    This prevents the bot from freezing when running heavy Pandas computations.
    """
    return await asyncio.to_thread(_fetch_fbref_sync, league_code, stat_type)


#==========≠========================÷÷÷÷÷

#====================================================

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu(selected_league: str = "ENG-Premier League"):
    """Builds interactive UI buttons for selecting leagues and stat modes."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", callback_data="league_ENG-Premier League"),
            InlineKeyboardButton("🇪🇸 La Liga", callback_data="league_ESP-La Liga")
        ],
        [
            InlineKeyboardButton("🇩🇪 Bundesliga", callback_data="league_GER-Bundesliga"),
            InlineKeyboardButton("🇮🇹 Serie A", callback_data="league_ITA-Serie A")
        ],
        [
            InlineKeyboardButton("⚙️ Standard Stats", callback_data=f"stat_standard_{selected_league}"),
            InlineKeyboardButton("⚽ Shooting Stats", callback_data=f"stat_shooting_{selected_league}")
        ],
        [
            InlineKeyboardButton("💾 System & DB Info", callback_data="menu_info")
        ]
    ])

#====================================================
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.enums import ParseMode

from vgx.database.food_db import save_user, get_cached_stat, set_cached_stat


def register_handlers(app: Client):

    @app.on_message(filters.command("stat_fd"))
    async def starfoodddt_cmd(client: Client, message: Message):
        # Register user in MongoDB
        await save_user(message.from_user.id, message.from_user.username or "Unknown")
        
        await message.reply_text(
            "⚽ **SoccerData Analytics Bot**\n\n"
            "Select a league or statistical category from the menu below:",
            reply_markup=get_main_menu()
        )

    # 🎯 REGEX CALLBACK ROUTER: Filters prefixes (league, stat, menu)
    @app.on_callback_query(filters.regex(r"^(league|stat|menu)_(.+)"))
    async def callback_router(client: Client, query: CallbackQuery):
        match = query.matches[0]
        prefix = match.group(1)  # Group 1: 'league', 'stat', or 'menu'
        value = match.group(2)   # Group 2: The parameters passed

        await save_user(query.from_user.id, query.from_user.username or "Unknown")

        # 1. Handle UI Info Screen
        if prefix == "menu" and value == "info":
            await query.answer("Fetching system info...")
            info_msg = (
                "💾 **MongoDB Status:** Connected & Active\n"
                "⚡ **Scraper:** `soccerdata` (FBref Module)\n"
                "👤 **User ID Saved:** `{}`".format(query.from_user.id)
            )
            await query.message.edit_text(
                info_msg,
                reply_markup=get_main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # 2. Handle League Selection Buttons
        if prefix == "league":
            await query.answer(f"Selected: {value}")
            await query.message.edit_text(f"⏳ **Loading data via soccerdata for {value}...**", parse_mode=ParseMode.MARKDOWN)

            cache_key = f"{value}_standard"
            cached = await get_cached_stat(cache_key)
            
            if cached:
                result_text = cached["data"]
            else:
                result_text = await get_fbref_stats(value, "standard")
                await set_cached_stat(cache_key, result_text)

            await query.message.edit_text(
                result_text,
                reply_markup=get_main_menu(selected_league=value),
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # 3. Handle Stat Category Selection Buttons
        if prefix == "stat":
            parts = value.split("_", 1)
            stat_type = parts[0]
            league_code = parts[1] if len(parts) > 1 else "ENG-Premier League"

            await query.answer(f"Loading {stat_type} stats...")
            await query.message.edit_text("⏳ **Processing DataFrames...**", parse_mode=ParseMode.MARKDOWN)

            cache_key = f"{league_code}_{stat_type}"
            cached = await get_cached_stat(cache_key)
            
            if cached:
                result_text = cached["data"]
            else:
                result_text = await get_fbref_stats(league_code, stat_type)
                await set_cached_stat(cache_key, result_text)

            await query.message.edit_text(
                result_text,
                reply_markup=get_main_menu(selected_league=league_code),
                parse_mode=ParseMode.MARKDOWN
            )
            return
