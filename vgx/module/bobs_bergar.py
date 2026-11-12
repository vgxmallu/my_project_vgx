import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app

# --- API ENDPOINT ---
API_URL = "https://bobsburgers-api.herokuapp.com/characters"

async def fetch_bobs_characters(limit: int = 12, skip: int = 572) -> list:
    """Fetches characters from the Bob's Burgers API asynchronously using httpx."""
    url = f"{API_URL}/?limit={limit}&skip={skip}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=15.0)
            if resp.status_code == 200:
                data = resp.json()
                # API returns a list directly
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "data" in data:
                    return data["data"]
            print(f"Bob's Burgers API Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"Bob's Burgers API Exception: {e}")
        return []


# --- COMMAND HANDLER ---

@app.on_message(filters.command(["bobsburgers", "bbchars", "bobsburgerschars"]))
async def cmd_bobs_burgers(client: Client, message: Message):
    """Command: /bobsburgers [skip] [limit] - Fetches characters from Bob's Burgers API."""
    args = message.command
    skip_val = 572  # Default to your requested skip value
    limit_val = 12   # Default limit

    # Allow custom arguments if provided (e.g., /bobsburgers 100 10)
    if len(args) > 1:
        try:
            skip_val = int(args[1])
        except ValueError:
            pass

    if len(args) > 2:
        try:
            limit_val = int(args[2])
        except ValueError:
            pass

    msg = await message.reply_text(f"🍔 Fetching Bob's Burgers characters (Skip: `{skip_val}`, Limit: `{limit_val}`)...")

    characters = await fetch_bobs_characters(limit=limit_val, skip=skip_val)
    if not characters:
        return await msg.edit_text("❌ No characters found or API request failed.")

    # Build formatted text output
    text = f"🍔 **Bob's Burgers Characters Database**\n📍 _Showing Skip: {skip_val} | Limit: {limit_val}_\n\n"
    
    for char in characters:
        c_id = char.get("id", "N/A")
        name = char.get("name", "Unknown")
        occupation = char.get("occupation", "Unknown")
        gender = char.get("gender", "N/A")
        wiki = char.get("wikiUrl", "")
        
        text += f"• **[{name}]({wiki})** (ID: `{c_id}`)\n"
        text += f"  - 💼 Occupation: `{occupation}`\n"
        text += f"  - ⚧ Gender: `{gender}`\n\n"

    # Pagination controls
    next_skip = skip_val + limit_val
    prev_skip = max(0, skip_val - limit_val)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⬅️ Previous", callback_data=f"bb_page_{prev_skip}_{limit_val}"),
            InlineKeyboardButton("➡️ Next", callback_data=f"bb_page_{next_skip}_{limit_val}")
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="bb_close")
        ]
    ])

    await msg.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


# --- INTERACTIVE PAGINATION CALLBACKS ---

@app.on_callback_query(filters.regex(r"^bb_page_(?P<skip>\d+)_(?P<limit>\d+)$"))
async def cb_bb_pagination(client: Client, query: CallbackQuery):
    await query.answer("Loading page...")
    match = query.matches[0]
    skip_val = int(match.group("skip"))
    limit_val = int(match.group("limit"))

    characters = await fetch_bobs_characters(limit=limit_val, skip=skip_val)
    if not characters:
        return await query.answer("No more characters available in this direction!", show_alert=True)

    text = f"🍔 **Bob's Burgers Characters Database**\n📍 _Showing Skip: {skip_val} | Limit: {limit_val}_\n\n"
    
    for char in characters:
        c_id = char.get("id", "N/A")
        name = char.get("name", "Unknown")
        occupation = char.get("occupation", "Unknown")
        gender = char.get("gender", "N/A")
        wiki = char.get("wikiUrl", "")
        
        text += f"• **[{name}]({wiki})** (ID: `{c_id}`)\n"
        text += f"  - 💼 Occupation: `{occupation}`\n"
        text += f"  - ⚧ Gender: `{gender}`\n\n"

    next_skip = skip_val + limit_val
    prev_skip = max(0, skip_val - limit_val)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⬅️ Previous", callback_data=f"bb_page_{prev_skip}_{limit_val}"),
            InlineKeyboardButton("➡️ Next", callback_data=f"bb_page_{next_skip}_{limit_val}")
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="close")
        ]
    ])

    await query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

