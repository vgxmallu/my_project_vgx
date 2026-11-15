import os
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config

# --- CONFIGURATION ---
SEVENDIGITAL_BASE_URL = "https://api.7digital.com/1.2"


def safe_truncate(text: str, max_length: int = 3800) -> str:
    """Safely truncates text to stay well within Telegram's 4000 character limit."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n\n... _(Output truncated due to length limitations)_"


async def sevendigital_request(endpoint: str, params: dict = None) -> dict:
    """Helper utility for asynchronous requests to the 7digital API via httpx (accepting JSON)."""
    headers = {
        "Accept": "application/json"
    }
    
    # Base parameters required for 7digital v1.2 public/hackathon endpoints
    query_params = {
        "oauth_consumer_key": getattr(Config, 'SEVENDIGITAL_CONSUMER_KEY', '7d4vr6cgb392'),
        "country": "us"
    }
    if params:
        query_params.update(params)

    url = f"{SEVENDIGITAL_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, params=query_params, headers=headers)
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "status": response.status_code, "error": safe_truncate(response.text, max_length=1500)}
        except Exception as e:
            return {"success": False, "status": 500, "error": str(e)}


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_sevendigital_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for 7digital Music Catalog controls."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Search Artist", callback_data="sd_search_artist_prompt"),
            InlineKeyboardButton("🎵 Search Release", callback_data="sd_search_release_prompt")
        ],
        [
            InlineKeyboardButton("📋 Browse Catalog", callback_data="sd_browse_prompt"),
            InlineKeyboardButton("📚 7digital Docs", url="https://7digital.gitbook.io/api-doc")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="sd_close")]
    ])


@app.on_message(filters.command(["sevendigital", "musicapi", "7digital"]))
async def cmd_sevendigital_dashboard(client: Client, message: Message):
    """Command: /sevendigital - Opens the master interactive 7digital Music API dashboard."""
    text = (
        "🎵 **7digital Music Intelligence Suite** [v1.2]\n\n"
        "Explore millions of tracks, browse artists, inspect album releases, and stream samples using "
        "the catalog navigation controls below:"
    )
    await message.reply_text(safe_truncate(text), reply_markup=get_sevendigital_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.command(["sdartist", "artistsearch"]))
async def cmd_sd_artist_search(client: Client, message: Message):
    """Command: /sdartist <query> - Searches the 7digital catalog for artists."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/sdartist <artist name>`\n\n_Example:_ `/sdartist coldplay`",
            parse_mode=ParseMode.MARKDOWN
        )

    query_term = message.text.partition(" ")[2].strip()
    msg = await message.reply_text(f"🔍 Searching 7digital artists for `{query_term}`...")

    res = await sevendigital_request("artist/search", {"q": query_term})
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="sd_home")]])

    if not res["success"]:
        return await msg.edit_text(
            f"❌ **API Request Failed** (`{res.get('status', 500)}`):\n`{safe_truncate(res['error'])}`\n\n"
            "_Tip: Check your consumer key configuration in `config.py`._",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

    data = res["data"]
    # Parse standard 7digital response structure safely
    search_results = data.get("searchResponse", {}).get("searchResults", {}).get("searchResult", [])
    
    if not search_results:
        return await msg.edit_text(f"📭 No artists found matching query: `{query_term}`", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    output = [f"🔍 **Artist Search Results:** `{query_term}`\n━━━━━━━━━━━━━━━━━━━━━━"]
    for item in search_results[:5]:
        artist = item.get("artist", {})
        name = artist.get("name", "Unknown Artist")
        artist_id = artist.get("id", "N/A")
        output.append(f"• **{name}** (ID: `{artist_id}`)")

    response_text = "\n".join(output)
    await msg.edit_text(safe_truncate(response_text), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^sd_home$"))
async def cb_sd_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🎵 **7digital Music Intelligence Suite** [v1.2]\n\n"
        "Explore millions of tracks, browse artists, inspect album releases, and stream samples using "
        "the catalog navigation controls below:"
    )
    await query.message.edit_text(safe_truncate(text), reply_markup=get_sevendigital_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^sd_search_artist_prompt$"))
async def cb_sd_artist_prompt(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="sd_home")]])
    text = (
        "🔍 **How to Search Artists:**\n\n"
        "Send the command directly in chat followed by your artist name keyword:\n"
        "`/sdartist adele` or `/sdartist ed sheeran`"
    )
    await query.message.edit_text(safe_truncate(text), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^sd_search_release_prompt$"))
async def cb_sd_release_prompt(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="sd_home")]])
    text = (
        "🎵 **Release Search Information:**\n\n"
        "Query releases and albums directly using the endpoint `release/search?q=...` combined with your 7digital consumer key."
    )
    await query.message.edit_text(safe_truncate(text), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^sd_browse_prompt$"))
async def cb_sd_browse_prompt(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="sd_home")]])
    text = (
        "📋 **Catalog Browsing (v1.2):**\n\n"
        "Use `artist/browse?letter=a` to list artists alphabetically or explore top charts via the standard REST endpoints."
    )
    await query.message.edit_text(safe_truncate(text), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^sd_close$"))
async def cb_sd_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
