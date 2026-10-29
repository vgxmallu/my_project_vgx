import os
import httpx
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config



BASE_URL = "https://api.football-data.org/v4/matches"
HEADERS = {"X-Auth-Token": Config.FOOTBALL_API_KEY}

# --- API FETCH HELPERS ---
async def fetch_matches_from_api(params: dict):
    """Fetches matches from football-data.org using async httpx with query parameters."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(BASE_URL, headers=HEADERS, params=params, timeout=10.0)
            if response.status_code == 429:
                return {"error": "⚠️ Rate limit exceeded. Please wait a minute."}
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"⚠️ HTTP Error: {e.response.status_code}"}
        except Exception as e:
            return {"error": f"⚠️ Connection Error: {str(e)}"}

async def fetch_single_match(match_id: int):
    """Fetches a specific match detail including referees and full metadata."""
    async with httpx.AsyncClient() as client:
        try:
            url = f"https://api.football-data.org/v4/matches/{match_id}"
            response = await client.get(url, headers=HEADERS, timeout=10.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None


# --- UI KEYBOARD BUILDERS ---
def get_main_menu(selected_date="TODAY", selected_comp="ALL", selected_status="ALL"):
    """Interactive control panel menu for filtering and navigation."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"📅 Date: {selected_date}", callback_data="m_menu_date"),
            InlineKeyboardButton(f"🏆 League: {selected_comp}", callback_data="m_menu_comp")
        ],
        [
            InlineKeyboardButton(f"📌 Status: {selected_status}", callback_data="m_menu_status"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"m_ref_{selected_date}_{selected_comp}_{selected_status}")
        ],
        [
            InlineKeyboardButton("❌ Close Panel", callback_data="m_close")
        ]
    ])

def get_date_selector_menu(comp, status):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏪ Yesterday", callback_data=f"m_set_date_YESTERDAY_{comp}_{status}"),
            InlineKeyboardButton("📅 Today", callback_data=f"m_set_date_TODAY_{comp}_{status}"),
            InlineKeyboardButton("⏩ Tomorrow", callback_data=f"m_set_date_TOMORROW_{comp}_{status}")
        ],
        [InlineKeyboardButton("⬅️ Back to Dashboard", callback_data=f"m_back_{comp}_{status}")]
    ])

def get_comp_selector_menu(date, status):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League (PL)", callback_data=f"m_set_comp_PL_{date}_{status}"),
            InlineKeyboardButton("🇪🇺 Champions League (CL)", callback_data=f"m_set_comp_CL_{date}_{status}")
        ],
        [
            InlineKeyboardButton("🇪🇸 La Liga (PD)", callback_data=f"m_set_comp_PD_{date}_{status}"),
            InlineKeyboardButton("🇩🇪 Bundesliga (BL1)", callback_data=f"m_set_comp_BL1_{date}_{status}")
        ],
        [
            InlineKeyboardButton("🇮🇹 Serie A (SA)", callback_data=f"m_set_comp_SA_{date}_{status}"),
            InlineKeyboardButton("🌐 All Leagues (ALL)", callback_data=f"m_set_comp_ALL_{date}_{status}")
        ],
        [InlineKeyboardButton("⬅️ Back to Dashboard", callback_data=f"m_back_{date}_{status}")]
    ])

def get_status_selector_menu(date, comp):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 All Statuses", callback_data=f"m_set_stat_ALL_{date}_{comp}"),
            InlineKeyboardButton("🏁 Finished Only", callback_data=f"m_set_stat_FINISHED_{date}_{comp}")
        ],
        [
            InlineKeyboardButton("⏳ Scheduled Only", callback_data=f"m_set_stat_SCHEDULED_{date}_{comp}"),
            InlineKeyboardButton("🔴 Live / In Play", callback_data=f"m_set_stat_IN_PLAY_{date}_{comp}")
        ],
        [InlineKeyboardButton("⬅️ Back to Dashboard", callback_data=f"m_back_{date}_{comp}")]
    ])


# --- COMMAND HANDLERS ---
@app.on_message(filters.command("fmatches"))
async def matcheufs_command(client: Client, message: Message):
    """Starts the interactive football matches dashboard."""
    date_filter = "TODAY"
    comp_filter = "ALL"
    status_filter = "ALL"
    
    # Build query params
    params = {"date": datetime.now().strftime("%Y-%m-%d")}
    
    data = await fetch_matches_from_api(params)
    if "error" in data:
        return await message.reply_text(data["error"])
        
    matches = data.get("matches", [])
    text = format_matches_list(matches, date_filter, comp_filter, status_filter)
    
    keyboard_buttons = [get_main_menu(date_filter, comp_filter, status_filter).inline_keyboard[0]] + \
                       [get_main_menu(date_filter, comp_filter, status_filter).inline_keyboard[1]] + \
                       [get_main_menu(date_filter, comp_filter, status_filter).inline_keyboard[2]] + \
                       build_match_selection_buttons(matches)

    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard_buttons), parse_mode=ParseMode.MARKDOWN)


# --- FORMATTERS ---
def format_matches_list(matches, date, comp, status):
    text = f"⚽ **Football Matches Control Center**\n"
    text += f"📅 Filter: `{date}` | 🏆 League: `{comp}` | 📌 Status: `{status}`\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if not matches:
        return text + "❌ No matches found matching your filters."
        
    for idx, match in enumerate(matches[:8], 1): # Limit list view to 8 items for UI neatness
        comp_name = match["competition"]["name"]
        home = match["homeTeam"]["shortName"]
        away = match["awayTeam"]["shortName"]
        match_status = match["status"]
        
        score_str = "[ vs ]"
        if match_status in ["FINISHED", "IN_PLAY", "PAUSED"]:
            home_ft = match["score"]["fullTime"]["home"]
            away_ft = match["score"]["fullTime"]["away"]
            score_str = f"[{home_ft} - {away_ft}]"
            
        text += f"**{idx}. {comp_name}**\n"
        text += f"⚽ {home} {score_str} {away} (`{match_status}`)\n"
        text += f"🆔 `ID: {match['id']}` | Click button below for deep info 👇\n\n"
        
    return text

def build_match_selection_buttons(matches):
    """Builds inline buttons to view specific match details by Match ID."""
    buttons = []
    row = []
    for idx, match in enumerate(matches[:8], 1):
        row.append(InlineKeyboardButton(f"🔍 Match #{idx}", callback_data=f"m_detail_{match['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    # Add footer control row
    buttons.append([InlineKeyboardButton("❌ Close Panel", callback_data="m_close")])
    return buttons


# --- STRICT REGEX CALLBACK QUERY ROUTERS ---

@app.on_callback_query(filters.regex(r"^m_menu_date$"))
async def cb_menu_date(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text("📅 **Select Date Range:**", reply_markup=get_date_selector_menu("ALL", "ALL"))

@app.on_callback_query(filters.regex(r"^m_menu_comp$"))
async def cb_menu_comp(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text("🏆 **Select Competition Code:**", reply_markup=get_comp_selector_menu("TODAY", "ALL"))

@app.on_callback_query(filters.regex(r"^m_menu_status$"))
async def cb_menu_status(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text("📌 **Select Match Status Filter:**", reply_markup=get_status_selector_menu("TODAY", "ALL"))

@app.on_callback_query(filters.regex(r"^m_set_date_(?P<date>YESTERDAY|TODAY|TOMORROW)_(?P<comp>[A-Z]+)_(?P<stat>[A-Z_]+)$"))
async def cb_set_date(client: Client, query: CallbackQuery):
    await query.answer("Fetching filtered matches...")
    date = query.matches[0].group("date")
    comp = query.matches[0].group("comp")
    stat = query.matches[0].group("stat")
    
    # Calculate date mapping
    today = datetime.now()
    if date == "YESTERDAY":
        target_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    elif date == "TOMORROW":
        target_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        target_date = today.strftime("%Y-%m-%d")
        
    params = {"date": target_date}
    if comp != "ALL":
        params["competitions"] = comp
    if stat != "ALL":
        params["status"] = stat
        
    data = await fetch_matches_from_api(params)
    if "error" in data:
        return await query.message.edit_text(data["error"])
        
    matches = data.get("matches", [])
    text = format_matches_list(matches, date, comp, stat)
    
    base_menu = get_main_menu(date, comp, stat).inline_keyboard
    kb_list = base_menu + build_match_selection_buttons(matches)
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb_list), parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^m_set_comp_(?P<comp>[A-Z]+)_(?P<date>[A-Z]+)_(?P<stat>[A-Z_]+)$"))
async def cb_set_comp(client: Client, query: CallbackQuery):
    await query.answer("Applying competition filter...")
    comp = query.matches[0].group("comp")
    date = query.matches[0].group("date")
    stat = query.matches[0].group("stat")
    
    today = datetime.now()
    if date == "YESTERDAY":
        target_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    elif date == "TOMORROW":
        target_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        target_date = today.strftime("%Y-%m-%d")
        
    params = {"date": target_date}
    if comp != "ALL":
        params["competitions"] = comp
    if stat != "ALL":
        params["status"] = stat
        
    data = await fetch_matches_from_api(params)
    if "error" in data:
        return await query.message.edit_text(data["error"])
        
    matches = data.get("matches", [])
    text = format_matches_list(matches, date, comp, stat)
    
    base_menu = get_main_menu(date, comp, stat).inline_keyboard
    kb_list = base_menu + build_match_selection_buttons(matches)
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb_list), parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^m_set_stat_(?P<stat>[A-Z_]+)_(?P<date>[A-Z]+)_(?P<comp>[A-Z]+)$"))
async def cb_set_stat(client: Client, query: CallbackQuery):
    await query.answer("Applying status filter...")
    stat = query.matches[0].group("stat")
    date = query.matches[0].group("date")
    comp = query.matches[0].group("comp")
    
    today = datetime.now()
    if date == "YESTERDAY":
        target_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    elif date == "TOMORROW":
        target_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        target_date = today.strftime("%Y-%m-%d")
        
    params = {"date": target_date}
    if comp != "ALL":
        params["competitions"] = comp
    if stat != "ALL":
        params["status"] = stat
        
    data = await fetch_matches_from_api(params)
    if "error" in data:
        return await query.message.edit_text(data["error"])
        
    matches = data.get("matches", [])
    text = format_matches_list(matches, date, comp, stat)
    
    base_menu = get_main_menu(date, comp, stat).inline_keyboard
    kb_list = base_menu + build_match_selection_buttons(matches)
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb_list), parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^m_detail_(?P<match_id>\d+)$"))
async def cb_match_detail(client: Client, query: CallbackQuery):
    """Displays comprehensive match metadata, team information, scores, and referee data."""
    await query.answer("Fetching deep match data...")
    match_id = int(query.matches[0].group("match_id"))
    
    match = await fetch_single_match(match_id)
    if not match:
        return await query.answer("❌ Could not retrieve match details.", show_alert=True)
        
    # Extracting Metadata
    utc_date = match.get("utcDate", "N/A")
    status = match.get("status", "N/A")
    matchday = match.get("matchday", "N/A")
    stage = match.get("stage", "N/A")
    group_stage = match.get("group")
    last_updated = match.get("lastUpdated", "N/A")
    
    # Competition & Area details
    comp = match.get("competition", {})
    comp_name = comp.get("name", "N/A")
    comp_code = comp.get("code", "N/A")
    area = comp.get("area", {}).get("name", "N/A")
    
    # Team Info (Home & Away)
    home = match.get("homeTeam", {})
    away = match.get("awayTeam", {})
    
    home_name = home.get("name", "Home")
    away_name = away.get("name", "Away")
    home_tla = home.get("tla", "HOM")
    away_tla = away.get("tla", "AWY")
    
    # Score Data
    score = match.get("score", {})
    winner = score.get("winner", "PENDING")
    duration = score.get("duration", "REGULAR")
    
    ft = score.get("fullTime", {})
    ht = score.get("halfTime", {})
    
    home_ft = ft.get("home", "-")
    away_ft = ft.get("away", "-")
    home_ht = ht.get("home", "-")
    away_ht = ht.get("home", "-")

# 🛠️ FIXED: Proper uniform indentation for Referee Data
    referees = match.get("referees", [])
    ref_text = ""
    if referees:
        for r in referees:
            ref_name = r.get("name", "Unknown")
            ref_role = r.get("role", "Referee")
            ref_nat = r.get("nationality", "N/A")
            ref_text += f"• {ref_name} ({ref_role} - {ref_nat})\n"
    else:
        ref_text = "• Referees not assigned yet.\n"

    # Construct Detailed Message Layout
    detail_msg = (
        f"📊 **Match Deep Analysis & Metadata**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 **Competition:** {comp_name} (`{comp_code}`) | 🌐 Area: {area}\n"
        f"📌 **Stage/Group:** {stage} {f'({group_stage})' if group_stage else ''} | Matchday: {matchday}\n"
        f"⏰ **Kickoff (UTC):** `{utc_date}`\n"
        f"🔄 **Status:** `{status}` | Last Updated: `{last_updated[:19]}`\n\n"
        f"🛡 **Team Information:**\n"
        f"🏠 **Home:** {home_name} (`{home_tla}`)\n"
        f"✈️ **Away:** {away_name} (`{away_tla}`)\n\n"
        f"⚽ **Scores & Outcomes:**\n"
        f"• Full-Time Score: **{home_ft} - {away_ft}**\n"
        f"• Half-Time Score: *{home_ht} - {away_ht}*\n"
        f"• Match Duration: `{duration}` | Result Winner: `{winner}`\n\n"
        f"⚖️ **Match Officials & Referees:**\n"
        f"{ref_text}"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 `Match Database ID: {match_id}`"
    )
    
    back_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Matches List", callback_data="m_back_TODAY_ALL")]
    ])
    
    await query.message.edit_text(detail_msg, reply_markup=back_markup, parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^m_back_(?P<date>[A-Z]+)_(?P<comp>[A-Z]+)$"))
async def cb_back_to_list(client: Client, query: CallbackQuery):
    await query.answer()
    date = query.matches[0].group("date")
    comp = query.matches[0].group("comp")
    
    today = datetime.now()
    if date == "YESTERDAY":
        target_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    elif date == "TOMORROW":
        target_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        target_date = today.strftime("%Y-%m-%d")
        
    params = {"date": target_date}
    if comp != "ALL":
        params["competitions"] = comp
        
    data = await fetch_matches_from_api(params)
    if "error" in data:
        return await query.message.edit_text(data["error"])
        
    matches = data.get("matches", [])
    text = format_matches_list(matches, date, comp, "ALL")
    
    base_menu = get_main_menu(date, comp, "ALL").inline_keyboard
    kb_list = base_menu + build_match_selection_buttons(matches)
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb_list), parse_mode=ParseMode.MARKDOWN)

