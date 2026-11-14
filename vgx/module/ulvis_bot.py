import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app

# --- CONFIGURATION ---
ULVIS_API_URL = "https://ulvis.net/api.php"
PERMANENT_CUSTOM_NAME = "x_botsx"


# --- ULVIS.NET API HELPER ---

async def shorten_url_via_ulvis(long_url: str) -> dict:
    """Sends a GET request to Ulvis.net API with permanent custom name 'x_botsx'."""
    params = {
        "url": long_url.strip(),
        "custom": PERMANENT_CUSTOM_NAME,
        "private": 1,
        "type": "json"
    }

    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            resp = await client.get(ULVIS_API_URL, params=params, timeout=15.0)
            if resp.status_code == 200:
                return resp.json()
            print(f"Ulvis API HTTP Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"Ulvis API Exception: {e}")
        return {}


# --- COMMAND HANDLER ---

@app.on_message(filters.command(["ulvis", "ulvisshort", "xbotsx"]))
async def cmd_ulvis_shorten(client: Client, message: Message):
    """Command: /ulvis <long_url> - Shortens a URL with permanent custom alias 'x_botsx'."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/ulvis <long_url>`\n\n"
            f"_Shortens your link with permanent custom alias:_ `{PERMANENT_CUSTOM_NAME}`",
            parse_mode=ParseMode.MARKDOWN
        )

    long_url = args[1].strip()
    if not long_url.startswith(("http://", "https://")):
        long_url = "https://" + long_url

    msg = await message.reply_text("🔗 Shortening link via Ulvis.net...")

    result = await shorten_url_via_ulvis(long_url)
    if not result:
        return await msg.edit_text("❌ Failed to connect to Ulvis.net API.")

    # Check Ulvis API JSON status
    if not result.get("success"):
        error_info = result.get("error", {})
        err_msg = error_info.get("msg") or error_info.get("url") or "Custom alias 'x_botsx' may already be taken or domain is blocked."
        return await msg.edit_text(f"❌ **Ulvis.net Error:** `{err_msg}`", parse_mode=ParseMode.MARKDOWN)

    data = result.get("data", {})
    short_url = data.get("url")
    link_id = data.get("id", PERMANENT_CUSTOM_NAME)

    if not short_url:
        return await msg.edit_text("❌ Invalid response received from Ulvis.net.")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Open Short Link", url=short_url)],
        [InlineKeyboardButton("❌ Close", callback_data="ulvis_close")]
    ])

    await msg.edit_text(
        f"✅ **Ulvis.net Short Link Created!**\n\n"
        f"• **Original:** `{long_url}`\n"
        f"• **Shortened:** `{short_url}`\n"
        f"• **Custom Alias:** `{link_id}`\n"
        f"• **Privacy:** `Private`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


# --- INTERACTIVE CALLBACK ROUTER ---

@app.on_callback_query(filters.regex(r"^ulvis_close$"))
async def cb_ulvis_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
