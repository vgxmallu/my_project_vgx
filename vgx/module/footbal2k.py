import asyncio
import io
import pandas as pd
import soccerdata as sd
import matplotlib.pyplot as plt

# --- 1. FBREF MODULE (Tactical Stats) ---
def _fetch_fbref_sync(league_code: str, mode: str) -> str:
    try:
        fbref = sd.FBref(leagues=league_code, seasons="2324")
        if mode == "keeper":
            df = fbref.read_team_season_stats(stat_type="keeper").reset_index()
            msg = f"🧤 **FBref Goalkeeping & PSxG ({league_code})**\n\n"
            msg += "`Team       | GA  | SoTA | Save%`\n`----------------------------`\n"
            for _, row in df.head(8).iterrows():
                team = str(row['team'])[:10].ljust(10)
                ga = str(row[('keeper', 'ga')]).ljust(3)
                sota = str(row[('keeper', 'sota')]).ljust(4)
                sv = str(row[('keeper', 'save_pct')]).ljust(4)
                msg += f"`{team} | {ga} | {sota} | {sv}%`\n"
            return msg
        else:
            df = fbref.read_team_season_stats(stat_type="standard").reset_index()
            msg = f"📊 **FBref Standard Stats ({league_code})**\n\n"
            msg += "`Team       | Pl  | Age | Poss `\n`----------------------------`\n"
            for _, row in df.head(8).iterrows():
                team = str(row['team'])[:10].ljust(10)
                pl = str(row[('standard', 'players_used')]).ljust(2)
                age = str(row[('standard', 'age')]).ljust(3)
                poss = str(row[('standard', 'possession')]).ljust(4)
                msg += f"`{team} | {pl} | {age} | {poss}%`\n"
            return msg
    except Exception as e:
        return f"⚠️ FBref Error: {str(e)}"

# --- 2. UNDERSTAT MODULE (Shot Maps & xG) ---
def _generate_understat_shotmap_sync(league_code: str) -> io.BytesIO:
    understat = sd.Understat(leagues=league_code, seasons="2324")
    shots_df = understat.read_shot_data()
    
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(shots_df['X'] * 100, shots_df['Y'] * 100, c='red', alpha=0.4, edgecolors='none')
    ax.set_title(f"xG Shot Map Locations - {league_code}")
    ax.set_facecolor('#1e1e1e')
    fig.patch.set_facecolor('#1e1e1e')
    ax.title.set_color('white')
    ax.tick_params(colors='white')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close(fig)
    return buf

# --- 3. CAPOLOGY MODULE (Salaries) ---
def _fetch_capology_sync(league_code: str) -> str:
    try:
        cap = sd.Capology(leagues=league_code, seasons="2324")
        df = cap.read_team_salaries().reset_index()
        msg = f"💰 **Capology Wage Bills ({league_code})**\n\n"
        msg += "`Team       | Gross/Yr (EUR)`\n`----------------------------`\n"
        for _, row in df.head(8).iterrows():
            team = str(row['team'])[:10].ljust(10)
            wage = f"€{row['gross_p_yr']:,}"
            msg += f"`{team} | {wage}`\n"
        return msg
    except Exception as e:
        return f"⚠️ Capology Error: {str(e)}"

# --- 4. SOFIFA MODULE (Ratings) ---
def _fetch_sofifa_sync(league_code: str) -> str:
    try:
        sofifa = sd.SoFIFA(leagues=league_code, seasons="2324")
        df = sofifa.read_ratings().reset_index()
        msg = f"🎮 **SoFIFA EA FC Ratings ({league_code})**\n\n"
        msg += "`Team       | OVR | ATT | MID | DEF`\n`----------------------------------`\n"
        for _, row in df.head(8).iterrows():
            team = str(row['team'])[:10].ljust(10)
            ovr = str(row['overall']).ljust(3)
            att = str(row['attack']).ljust(3)
            mid = str(row['midfield']).ljust(3)
            defn = str(row['defense']).ljust(3)
            msg += f"`{team} | {ovr} | {att} | {mid} | {defn}`\n"
        return msg
    except Exception as e:
        return f"⚠️ SoFIFA Error: {str(e)}"

# --- 5. CLUBELO MODULE (Global Power Rankings) ---
def _fetch_clubelo_sync() -> str:
    try:
        elo = sd.ClubElo()
        df = elo.read_by_date().reset_index()
        msg = "📈 **Global ClubElo Power Rankings**\n\n"
        msg += "`#  | Club       | Elo Rating`\n`----------------------------`\n"
        for _, row in df.head(10).iterrows():
            rank = str(row['rank']).ljust(2)
            club = str(row['club'])[:10].ljust(10)
            rating = str(int(row['elo'])).ljust(4)
            msg += f"`{rank} | {club} | {rating}`\n"
        return msg
    except Exception as e:
        return f"⚠️ ClubElo Error: {str(e)}"

# --- 6. MATCHHISTORY MODULE (Odds & Cards) ---
def _fetch_matchhistory_sync(league_code: str) -> str:
    try:
        mh = sd.MatchHistory(leagues=league_code, seasons="2324")
        df = mh.read_games().reset_index()
        msg = f"🎲 **MatchHistory Stats ({league_code})**\n\n"
        msg += "`Home vs Away       | HY | AY | Ref`\n`----------------------------------`\n"
        for _, row in df.head(6).iterrows():
            match_name = f"{str(row['home_team'])[:4]}v{str(row['away_team'])[:4]}".ljust(18)
            hy = str(row.get('HY', 0)).ljust(2)
            ay = str(row.get('AY', 0)).ljust(2)
            ref = str(row.get('referee', 'N/A'))[:6]
            msg += f"`{match_name} | {hy} | {ay} | {ref}`\n"
        return msg
    except Exception as e:
        return f"⚠️ MatchHistory Error: {str(e)}"

# --- ASYNC THREADED WRAPPERS ---
async def get_fbref_stats(league="ENG-Premier League", mode="standard"):
    return await asyncio.to_thread(_fetch_fbref_sync, league, mode)

async def get_understat_shotmap(league="ENG-Premier League"):
    return await asyncio.to_thread(_generate_understat_shotmap_sync, league)

async def get_capology_salaries(league="ENG-Premier League"):
    return await asyncio.to_thread(_fetch_capology_sync, league)

async def get_sofifa_ratings(league="ENG-Premier League"):
    return await asyncio.to_thread(_fetch_sofifa_sync, league)

async def get_clubelo_rankings():
    return await asyncio.to_thread(_fetch_clubelo_sync)

async def get_matchhistory_stats(league="ENG-Premier League"):
    return await asyncio.to_thread(_fetch_matchhistory_sync, league)

#====================================================
#====================================================

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_engine_menu():
    """Main menu to choose from soccerdata engines."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 FBref Analytics", callback_data="eng_fbref"),
            InlineKeyboardButton("🎯 Understat xG Map", callback_data="eng_understat")
        ],
        [
            InlineKeyboardButton("💰 Capology Salaries", callback_data="eng_capology"),
            InlineKeyboardButton("🎮 SoFIFA Ratings", callback_data="eng_sofifa")
        ],
        [
            InlineKeyboardButton("📈 ClubElo Rankings", callback_data="eng_clubelo"),
            InlineKeyboardButton("🎲 Match History", callback_data="eng_matchhistory")
        ]
    ])

def get_league_menu(engine_prefix: str):
    """Sub-menu dynamically generated for league selection across engines."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", callback_data=f"sub_{engine_prefix}_ENG-Premier League"),
            InlineKeyboardButton("🇪🇸 La Liga", callback_data=f"sub_{engine_prefix}_ESP-La Liga")
        ],
        [
            InlineKeyboardButton("🇩🇪 Bundesliga", callback_data=f"sub_{engine_prefix}_GER-Bundesliga"),
            InlineKeyboardButton("🇮🇹 Serie A", callback_data=f"sub_{engine_prefix}_ITA-Serie A")
        ],
        [
            InlineKeyboardButton("🔙 Back to Engines", callback_data="eng_main")
        ]
    ])

#====================================================
#====================================================

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.enums import ParseMode

from vgx.database.food_db import save_user, get_cached_data, set_cached_data
from vgx import app


def register_handlers(app: Client):

@app.on_message(filters.command("footbal"))
async def start_footcmd(client: Client, message: Message):
    await save_user(message.from_user.id, message.from_user.username or "Unknown")
    await message.reply_text(
        "⚽ **Ultimate SoccerData Engine Bot**\n\n"
        "Choose a statistical scraping engine to query data from:",
        reply_markup=get_engine_menu()
    )

    # 🎯 REGEX CALLBACK ROUTER: Intercepts engine navigation and sub-action triggers
    @app.on_callback_query(filters.regex(r"^(eng|sub)_(.+)"))
    async def main_callback_router(client: Client, query: CallbackQuery):
        match = query.matches[0]
        prefix = match.group(1)  # 'eng' or 'sub'
        value = match.group(2)   # Target module or combined parameters

        await save_user(query.from_user.id, query.from_user.username or "Unknown")

        # 1. Main Navigation Routing
        if prefix == "eng":
            if value == "main":
                await query.message.edit_text("Select an engine:", reply_markup=get_engine_menu())
                return

            if value == "clubelo":
                await query.answer("Fetching ClubElo data...")
                await query.message.edit_text("⏳ **Scraping ClubElo Power Rankings...**", parse_mode=ParseMode.MARKDOWN)
                
                cached = await get_cached_data("clubelo")
                res = cached["data"] if cached else await get_clubelo_rankings()
                if not cached:
                    await set_cached_data("clubelo", res)
                
                await query.message.edit_text(res, reply_markup=get_engine_menu(), parse_mode=ParseMode.MARKDOWN)
                return

            # Display league menu for engines requiring a targeted league
            await query.message.edit_text(
                f"Select a league for **{value.upper()}**:",
                reply_markup=get_league_menu(value)
            )
            return

        # 2. Sub-Category Engine Action Execution
        if prefix == "sub":
            parts = value.split("_", 1)
            engine = parts[0]
            league = parts[1]

            await query.answer(f"Loading {engine} for {league}...")
            await query.message.edit_text(f"⏳ **Processing Data via {engine.upper()}...**", parse_mode=ParseMode.MARKDOWN)

            cache_key = f"{engine}_{league}"
            
            # --- ENGINE ROUTING LOGIC ---
            if engine == "understat":
                photo_buf = await get_understat_shotmap(league)
                await query.message.reply_photo(photo=photo_buf, caption=f"🎯 Shot Map: {league}")
                await query.message.delete()
                return

            cached = await get_cached_data(cache_key)
            if cached:
                result_text = cached["data"]
            else:
                if engine == "fbref":
                    result_text = await get_fbref_stats(league, "standard")
                elif engine == "capology":
                    result_text = await get_capology_salaries(league)
                elif engine == "sofifa":
                    result_text = await get_sofifa_ratings(league)
                elif engine == "matchhistory":
                    result_text = await get_matchhistory_stats(league)
                else:
                    result_text = "⚠️ Unknown Engine Request."
                
                await set_cached_data(cache_key, result_text)

            await query.message.edit_text(
                result_text,
                reply_markup=get_engine_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
            return


