import httpx
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from vgx import app

# Radio Browser stable mirror base URL
BASE_URL = "https://de1.api.radio-browser.info/json"

# Radio Browser API requires a speaking User-Agent header
HEADERS = {
    "User-Agent": "TelegramRadioBot/1.0 (Python Pyrogram)"
}

# In-memory session cache to store active user search results for button navigation
RADIO_SESSIONS = {}

# --- API HELPER FUNCTION ---
async def call_radio_api(endpoint: str, params: dict = None):
    """Asynchronously queries the Radio Browser API."""
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        try:
            resp = await client.get(url, params=params, timeout=12.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Radio Browser API Error [{url}]: {e}")
            return None


# --- COMMAND HANDLERS ---

@app.on_message(filters.command(["rs", "searchradio"]))
async def cmd_sebarch_radio(client: Client, message: Message):
    """Command: /radiosearch <station_name> - Searches radio stations by name."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/radiosearch station_name`\n_Example:_ `/radiosearch BBC` or `/radiosearch Jazz`")

    query = " ".join(args[1:])
    msg = await message.reply_text(f"🔍 Searching radio stations for `{query}`...")

    # Search endpoint filtering out broken stations
    params = {"name": query, "limit": 10, "hidebroken": "true"}
    stations = await call_radio_api("stations/search", params)

    if not stations:
        return await msg.edit_text(f"❌ No active radio stations found matching `{query}`.")

    text = f"📻 **Search Results for:** `{query}`\n\n"
    for idx, station in enumerate(stations, 1):
        name = station.get("name", "Unknown Station").strip()
        country = station.get("country", "Unknown")
        codec = station.get("codec", "N/A").upper()
        bitrate = station.get("bitrate", "0")
        stream_url = station.get("url_resolved") or station.get("url")
        
        text += f"{idx}. **{name}** ({country})\n"
        text += f"   • Codec: `{codec}` | Bitrate: `{bitrate} kbps`\n"
        text += f"   • [Direct Stream Link]({stream_url})\n\n"

    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


@app.on_message(filters.command(["rc", "countryradio"]))
async def cmd_radio_vby_country(client: Client, message: Message):
    """Command: /radiocountry <country_name> - Finds top-voted stations by country."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/radiocountry country_name`\n_Example:_ `/radiocountry United States` or `/radiocountry Germany`")

    country = " ".join(args[1:])
    msg = await message.reply_text(f"🔍 Finding top radio stations in `{country}`...")

    params = {"country": country, "limit": 10, "hidebroken": "true", "order": "votes", "reverse": "true"}
    stations = await call_radio_api("stations/search", params)

    if not stations:
        return await msg.edit_text(f"❌ No active stations found for country `{country}`. Check your spelling or try standard country names.")

    text = f"📻 **Top Stations in {country.capitalize()}**\n\n"
    for idx, station in enumerate(stations, 1):
        name = station.get("name", "Unknown Station").strip()
        votes = station.get("votes", 0)
        stream_url = station.get("url_resolved") or station.get("url")
        
        text += f"{idx}. **{name}** (❤️ {votes} votes)\n"
        text += f"   • [Direct Stream Link]({stream_url})\n\n"

    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


@app.on_message(filters.command(["radiotag", "genreradio"]))
async def cmd_radio_by_tag(client: Client, message: Message):
    """Command: /radiotag <genre> - Finds stations by music genre or tag."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/radiotag genre`\n_Example:_ `/radiotag rock`, `/radiotag jazz`, or `/radiotag classical`")

    tag = args[1].lower()
    msg = await message.reply_text(f"🔍 Finding `{tag}` radio stations...")

    params = {"tag": tag, "limit": 10, "hidebroken": "true", "order": "votes", "reverse": "true"}
    stations = await call_radio_api("stations/search", params)

    if not stations:
        return await msg.edit_text(f"❌ No active stations found for genre/tag `{tag}`.")

    text = f"📻 **Top Stations for Genre:** `{tag.capitalize()}`\n\n"
    for idx, station in enumerate(stations, 1):
        name = station.get("name", "Unknown Station").strip()
        country = station.get("country", "Unknown")
        stream_url = station.get("url_resolved") or station.get("url")
        
        text += f"{idx}. **{name}** ({country})\n"
        text += f"   • [Direct Stream Link]({stream_url})\n\n"

    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

#====================================================

# Radio Browser stable mirror base URL


# --- UI KEYBOARD BUILDERS ---
def get_main_radio_menu():
    """Main interactive hub for Radio Browser."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔥 Top Voted Stations", callback_data="rd_top_0", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("🎵 Browse by Genre", callback_data="rd_genres", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("🌍 Browse by Country", callback_data="rd_countries", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("🔍 Search Guide", callback_data="rd_help", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("❌ Close Menu", callback_data="close", style=ButtonStyle.DANGER)
        ]
    ])


def get_genre_menu():
    """Quick music genre selection menu."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎸 Rock", callback_data="rd_tag_rock", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("🎷 Jazz", callback_data="rd_tag_jazz", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("🎹 Classical", callback_data="rd_tag_classical", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("🎧 Electronic", callback_data="rd_tag_electronic", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("📻 Pop", callback_data="rd_tag_pop", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("🎸 Metal", callback_data="rd_tag_metal", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("🏠 Main Hub", callback_data="rd_home", style=ButtonStyle.PRIMARY)
        ]
    ])


def get_country_menu():
    """Quick country selection menu."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇺🇸 United States", callback_data="rd_country_United States", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("🇬🇧 United Kingdom", callback_data="rd_country_United Kingdom", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("🇩🇪 Germany", callback_data="rd_country_Germany", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("🇫🇷 France", callback_data="rd_country_France", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("🇮🇳 India", callback_data="rd_country_India", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("🇯🇵 Japan", callback_data="rd_country_Japan", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("🏠 Main Hub", callback_data="rd_home", style=ButtonStyle.PRIMARY)
        ]
    ])


def get_station_card_keyboard(index: int, total: int, stream_url: str):
    """Pagination and stream action keyboard for station browsing."""
    prev_idx = max(0, index - 1)
    next_idx = min(total - 1, index + 1)

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶️ Open Direct Stream", url=stream_url, style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("⬅️ Prev", callback_data=f"rd_nav_{prev_idx}", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton(f"📖 {index + 1} / {total}", callback_data="rd_noop", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("Next ➡️", callback_data=f"rd_nav_{next_idx}", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("🏠 Main Hub", callback_data="rd_home", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("❌ Close", callback_data="close", style=ButtonStyle.DANGER)
        ]
    ])


# --- COMMAND HANDLERS ---

@app.on_message(filters.command(["radio", "radiohub"]))
async def cmd_radio_hub(client: Client, message: Message):
    """Command: /radio or /radiohub - Opens the interactive radio control center."""
    text = (
        "📻 **Radio Browser — Control Center**\n\n"
        "Welcome! Stream over 45,000+ live global radio stations instantly.\n\n"
        "👇 **Select an option below or use search commands:**\n"
        "• `/radiosearch name`\n"
        "• `/radiocountry country`\n"
        "• `/radiotag genre`"
    )
    await message.reply_text(text, reply_markup=get_main_radio_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["radiosearch", "ss"]))
async def cmd_search_radio(client: Client, message: Message):
    """Command: /radiosearch <name> - Interactive text search."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/radiosearch station_name`\n_Example:_ `/radiosearch BBC`")

    query = " ".join(args[1:])
    msg = await message.reply_text(f"🔍 Searching radio stations for `{query}`...")

    params = {"name": query, "limit": 15, "hidebroken": "true", "order": "votes", "reverse": "true"}
    stations = await call_radio_api("stations/search", params)

    if not stations:
        return await msg.edit_text(f"❌ No active radio stations found matching `{query}`.")

    user_id = message.from_user.id
    RADIO_SESSIONS[user_id] = stations

    await show_station_card(client, msg, user_id, 0, is_edit=True)


async def show_station_card(client, message, user_id: int, idx: int, is_edit: bool = False):
    """Renders an individual station card with interactive navigation."""
    stations = RADIO_SESSIONS.get(user_id, [])
    if not stations:
        text = "⚠️ Session expired or no stations available. Please search again!"
        if is_edit:
            return await message.edit_text(text)
        return await message.reply_text(text)

    if idx >= len(stations):
        idx = 0

    st = stations[idx]
    name = st.get("name", "Unknown Station").strip()
    country = st.get("country", "Unknown")
    codec = st.get("codec", "N/A").upper()
    bitrate = st.get("bitrate", "0")
    votes = st.get("votes", 0)
    stream_url = st.get("url_resolved") or st.get("url")
    homepage = st.get("homepage", "")

    text = (
        f"📻 **Station Profile ({idx + 1}/{len(stations)})**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎵 **Name:** `{name}`\n"
        f"🌍 **Country:** `{country}`\n"
        f"🔊 **Codec:** `{codec}` | **Bitrate:** `{bitrate} kbps`\n"
        f"❤️ **Votes:** `{votes}`\n"
    )
    if homepage:
        text += f"🌐 **Website:** {homepage}\n"

    kb = get_station_card_keyboard(idx, len(stations), stream_url)

    if is_edit:
        await message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    else:
        await message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


# --- STRICT CALLBACK QUERY ROUTERS ---

@app.on_callback_query(filters.regex(r"^rd_home$"))
async def cb_rd_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "📻 **Radio Browser — Control Center**\n\n"
        "Welcome! Stream over 45,000+ live global radio stations instantly.\n\n"
        "👇 **Select an option below or use search commands:**"
    )
    await query.message.edit_text(text, reply_markup=get_main_radio_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^rd_noop$"))
async def cb_rd_noop(client: Client, query: CallbackQuery):
    await query.answer("📌 Station position", show_alert=False)

@app.on_callback_query(filters.regex(r"^rd_genres$"))
async def cb_rd_genres(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(
        "🎵 **Browse by Music Genre**\n\nSelect a genre below to explore top-rated stations:",
        reply_markup=get_genre_menu(),
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_callback_query(filters.regex(r"^rd_countries$"))
async def cb_rd_countries(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(
        "🌍 **Browse by Country**\n\nSelect a country below to explore top-rated stations:",
        reply_markup=get_country_menu(),
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_callback_query(filters.regex(r"^rd_help$"))
async def cb_rd_help(client: Client, query: CallbackQuery):
    await query.answer()
    help_text = (
        "📖 **Radio Browser — Command Guide**\n\n"
        "• `/radiosearch <name>` — Search by name.\n"
        "• `/radiocountry <country>` — Find stations by country.\n"
        "• `/radiotag <genre>` — Find stations by genre.\n"
        "• `/radio` — Open interactive dashboard."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Hub", callback_data="rd_home", style=ButtonStyle.PRIMARY)]])
    await query.message.edit_text(help_text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^rd_top_0$"))
async def cb_rd_top(client: Client, query: CallbackQuery):
    await query.answer("Loading top voted stations...")
    params = {"limit": 20, "hidebroken": "true", "order": "votes", "reverse": "true"}
    stations = await call_radio_api("stations/search", params)
    
    if not stations:
        return await query.answer("❌ Failed to fetch top stations.", show_alert=True)

    user_id = query.from_user.id
    RADIO_SESSIONS[user_id] = stations
    await show_station_card(client, query.message, user_id, 0, is_edit=True)

@app.on_callback_query(filters.regex(r"^rd_tag_(?P<tag>[a-zA-Z]+)$"))
async def cb_rd_tag(client: Client, query: CallbackQuery):
    tag = query.matches[0].group("tag")
    await query.answer(f"Loading {tag} stations...")
    
    params = {"tag": tag, "limit": 15, "hidebroken": "true", "order": "votes", "reverse": "true"}
    stations = await call_radio_api("stations/search", params)

    if not stations:
        return await query.answer(f"❌ No stations found for {tag}.", show_alert=True)

    user_id = query.from_user.id
    RADIO_SESSIONS[user_id] = stations
    await show_station_card(client, query.message, user_id, 0, is_edit=True)

@app.on_callback_query(filters.regex(r"^rd_country_(?P<country>.+)$"))
async def cb_rd_country(client: Client, query: CallbackQuery):
    country = query.matches[0].group("country")
    await query.answer(f"Loading stations in {country}...")
    
    params = {"country": country, "limit": 15, "hidebroken": "true", "order": "votes", "reverse": "true"}
    stations = await call_radio_api("stations/search", params)

    if not stations:
        return await query.answer(f"❌ No stations found for {country}.", show_alert=True)

    user_id = query.from_user.id
    RADIO_SESSIONS[user_id] = stations
    await show_station_card(client, query.message, user_id, 0, is_edit=True)

@app.on_callback_query(filters.regex(r"^rd_nav_(?P<idx>\d+)$"))
async def cb_rd_nav(client: Client, query: CallbackQuery):
    idx = int(query.matches[0].group("idx"))
    user_id = query.from_user.id
    await query.answer()
    await show_station_card(client, query.message, user_id, idx, is_edit=True)

