import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app

# --- API BASE URL ---
BTVS_BASE = "https://buffy-angel-api.onrender.com"

async def fetch_btvs(endpoint: str) -> any:
    """Asynchronous helper to fetch data from the BTVS & Angel API."""
    url = f"{BTVS_BASE}/{endpoint.lstrip('/')}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=15.0)
            if resp.status_code == 200:
                return resp.json()
            print(f"BTVS API Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"BTVS API Exception: {e}")
        return None


# --- UI KEYBOARD BUILDERS (Inline Only) ---

def get_buffy_main_menu():
    """Main interactive dashboard UI built entirely with Inline Keyboards."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👥 Characters", callback_data="btvs_menu_chars"),
            InlineKeyboardButton("💬 Random Quote", callback_data="btvs_menu_quote")
        ],
        [
            InlineKeyboardButton("ℹ️ API Info", callback_data="btvs_menu_about"),
            InlineKeyboardButton("❌ Close Menu", callback_data="btvs_close")
        ]
    ])


# --- COMMAND HANDLER ---

@app.on_message(filters.command(["buffy", "btvs", "buffybot"]))
async def cmd_buffy_main(client: Client, message: Message):
    """Command: /buffy - Opens the Buffy & Angel API interactive dashboard."""
    text = (
        "🧛‍♀️ **Buffy the Vampire Slayer & Angel API Hub**\n\n"
        "Welcome to the Hellmouth! Explore characters, quotes, and lore from the Buffyverse using the interactive buttons below:"
    )
    await message.reply_text(text, reply_markup=get_buffy_main_menu(), parse_mode=ParseMode.MARKDOWN)


# --- INTERACTIVE CALLBACK ROUTERS ---

@app.on_callback_query(filters.regex(r"^btvs_menu_main$"))
async def cb_btvs_main(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🧛‍♀️ **Buffy the Vampire Slayer & Angel API Hub**\n\n"
        "Welcome back to the dashboard! Select an option below:"
    )
    await query.message.edit_text(text, reply_markup=get_buffy_main_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^btvs_menu_chars$"))
async def cb_btvs_chars(client: Client, query: CallbackQuery):
    await query.answer("Loading characters...")
    data = await fetch_btvs("characters")
    
    if not data or not isinstance(data, list):
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="btvs_menu_main")]])
        return await query.message.edit_text("❌ Failed to load characters from the API.", reply_markup=keyboard)

    # Display top 10 characters interactively
    chars = data[:10]
    text = "👥 **Buffyverse Characters (Top 10)**\n\n"
    for idx, c in enumerate(chars, 1):
        name = c.get("name", "Unknown")
        role = c.get("role", "N/A")
        species = c.get("species", "N/A")
        text += f"{idx}. **{name}** — `{role}` ({species})\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh List", callback_data="btvs_menu_chars")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="btvs_menu_main")]
    ])
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^btvs_menu_quote$"))
async def cb_btvs_quote(client: Client, query: CallbackQuery):
    await query.answer("Fetching a random quote...")
    data = await fetch_btvs("quotes/random")
    
    if not data:
        quote_text = "I'm the thing that monsters have nightmares about."
        source = "Buffy Summers"
    else:
        quote_item = data[0] if isinstance(data, list) and data else data
        quote_text = quote_item.get("quote", "No quote found.")
        source = quote_item.get("source", "Unknown character")

    text = (
        f"💬 **Buffyverse Quote Generator**\n\n"
        f"> *\"{quote_text}\"*\n\n"
        f"— **{source}**"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔀 Another Quote", callback_data="btvs_menu_quote")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="btvs_menu_main")]
    ])
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^btvs_menu_about$"))
async def cb_btvs_about(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "ℹ️ **About BTVS & Angel API**\n\n"
        "A public API providing episode summaries, cast data, crew lists, and quotes from *Buffy the Vampire Slayer* and its spin-off *Angel*.\n\n"
        "Repository: [Thatskat/btvs-angel-api](https://github.com/Thatskat/btvs-angel-api)"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="btvs_menu_main")]
    ])
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^btvs_close$"))
async def cb_btvs_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
