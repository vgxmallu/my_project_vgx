import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app

# --- CONFIGURATION & ENDPOINT ---
ULVIS_API_URL = "https://ulvis.net/api.php"

# Realistic browser headers to bypass strict basic Cloudflare filtering
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://ulvis.net/",
    "X-Requested-With": "XMLHttpRequest"
}


# --- ULVIS.NET API HELPER ---

async def shorten_url_via_ulvis(long_url: str, custom_name: str = None) -> dict:
    """Sends a GET request to Ulvis.net API with spoofed browser headers."""
    params = {
        "url": long_url.strip(),
        "private": 1,
        "type": "json"
    }
    if custom_name:
        params["custom"] = custom_name.strip()

    # Using an async client with cookies and proper headers
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        try:
            resp = await client.get(ULVIS_API_URL, params=params, timeout=15.0)
            
            # Check if Cloudflare HTML challenge page is returned instead of JSON
            if "text/html" in resp.headers.get("content-type", ""):
                print("Ulvis API Blocked: Cloudflare challenge page encountered.")
                return {"error": "Cloudflare security challenge triggered. Ulvis.net is blocking automated requests from this server IP."}

            if resp.status_code == 200:
                return resp.json()
            
            print(f"Ulvis API HTTP Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"Ulvis API Exception: {e}")
            
        return {}


# --- COMMAND HANDLER ---

@app.on_message(filters.command(["ulvis", "ulvisshort"]))
async def cmd_ulvis_shorten(client: Client, message: Message):
    """Command: /ulvis <long_url> [custom_name] - Shortens a URL via Ulvis.net."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/ulvis <long_url> [custom_name]`\n\n"
            "_Example:_ `/ulvis https://example.com my-custom-alias`",
            parse_mode=ParseMode.MARKDOWN
        )

    long_url = args[1].strip()
    custom_name = args[2].strip() if len(args) > 2 else None

    if not long_url.startswith(("http://", "https://")):
        long_url = "https://" + long_url

    msg = await message.reply_text("🔗 Shortening link via Ulvis.net...")

    result = await shorten_url_via_ulvis(long_url, custom_name)
    if not result:
        return await msg.edit_text("❌ Failed to connect to Ulvis.net API.")

    if "error" in result and isinstance(result["error"], str):
        return await msg.edit_text(f"❌ **Blocked:** `{result['error']}`", parse_mode=ParseMode.MARKDOWN)

    if not result.get("success"):
        error_info = result.get("error", {})
        err_msg = error_info.get("msg") or error_info.get("url") or "Custom alias may already be taken or blocked."
        return await msg.edit_text(f"❌ **Ulvis.net Error:** `{err_msg}`", parse_mode=ParseMode.MARKDOWN)

    data = result.get("data", {})
    short_url = data.get("url")

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
        f"• **Custom Name:** `{custom_name or 'Auto-generated'}`\n"
        f"• **Privacy:** `Private (1)`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


# --- INTERACTIVE CALLBACK ROUTER ---

@app.on_callback_query(filters.regex(r"^ulvis_close$"))
async def cb_ulvis_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
