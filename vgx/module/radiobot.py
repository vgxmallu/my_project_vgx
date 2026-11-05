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

@app.on_message(filters.command(["radiosearch", "searchradio"]))
async def cmd_search_radio(client: Client, message: Message):
    """Command: /radiosearch <station_name> - Searches radio stations by name."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/radiosearch <station_name>`\n_Example:_ `/radiosearch BBC` or `/radiosearch Jazz`")

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


@app.on_message(filters.command(["radiocountry", "countryradio"]))
async def cmd_radio_by_country(client: Client, message: Message):
    """Command: /radiocountry <country_name> - Finds top-voted stations by country."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/radiocountry <country_name>`\n_Example:_ `/radiocountry United States` or `/radiocountry Germany`")

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
        return await message.reply_text("⚠️ **Usage:** `/radiotag <genre>`\n_Example:_ `/radiotag rock`, `/radiotag jazz`, or `/radiotag classical`")

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


@app.on_message(filters.command("radiohelp"))
async def cmd_radio_help(client: Client, message: Message):
    """Command: /radiohelp - Displays command guide for the Radio Browser bot."""
    help_text = (
        "📖 **Radio Browser Bot — Command Guide**\n\n"
        "• `/radiosearch <name>` — Search radio stations by name (e.g., `/radiosearch BBC`).\n"
        "• `/radiocountry <country>` — Find top stations by country (e.g., `/radiocountry United States`).\n"
        "• `/radiotag <genre>` — Find stations by music genre/tag (e.g., `/radiotag jazz`).\n"
        "• `/radiohelp` — View this command guide.\n\n"
        "_Powered by Radio Browser API (45,000+ free stations worldwide — No API key required!)_"
    )
    await message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
