import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config  # Must contain BLY_API_KEY

# --- CONFIGURATION & ENDPOINTS ---
BLY_BASE = "https://bly.to"

def get_bly_token() -> str:
    """Retrieves the Bly.to API key from config safely."""
    return getattr(Config, "BLY_API_KEY", None))


# --- BLY.TO API HELPER ---

async def shorten_url_via_bly(long_url: str, slug: str = None, qr: bool = True) -> dict:
    """Sends a POST request to Bly.to API to shorten a long URL."""
    api_key = get_bly_token()
    if not api_key:
        return {"error": "Missing API token"}

    endpoint = f"{BLY_BASE}/shorten"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key
    }
    payload = {"long": long_url.strip()}
    if slug:
        payload["slug"] = slug.strip()
    if qr:
        payload["qr"] = True

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(endpoint, json=payload, headers=headers, timeout=15.0)
            if resp.status_code in [200, 201]:
                return resp.json()
            print(f"Bly.to API Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"Bly.to API Exception: {e}")
        return {}


# --- COMMAND HANDLER ---

@app.on_message(filters.command(["bly", "blyshort", "shortenbly"]))
async def cmd_bly_shorten(client: Client, message: Message):
    """Command: /bly <url> [custom_slug] - Shortens a long URL using Bly.to."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/bly long_url [custom_slug]`\n\n"
            "_Example:_ `/bly https://github.com/vgxmallu/my_project_vgx my-custom-link`",
            parse_mode=ParseMode.MARKDOWN
        )

    long_url = args[1].strip()
    slug = args[2].strip() if len(args) > 2 else None

    if not long_url.startswith(("http://", "https://")):
        long_url = "https://" + long_url

    msg = await message.reply_text("🔗 Generating short link via Bly.to...")

    result = await shorten_url_via_bly(long_url, slug=slug, qr=True)
    if not result or "error" in result:
        return await msg.edit_text("❌ Failed to shorten URL. Check your `BLY_API_KEY` in `config.py` or try a different slug.")

    # Extract dynamic response fields safely
    short_link = result.get("shortUrl") or result.get("link") or result.get("url") or result.get("short")
    qr_url = result.get("qrUrl") or result.get("qr_url")

    if not short_link:
        return await msg.edit_text("❌ Received an invalid response structure from Bly.to API.")

    # Inline keyboard action buttons
    keyboard_buttons = [
        [InlineKeyboardButton("🌐 Open Short Link", url=short_link)]
    ]
    if qr_url:
        keyboard_buttons.append([InlineKeyboardButton("📱 View QR Code", url=qr_url)])
    
    keyboard_buttons.append([InlineKeyboardButton("❌ Close", callback_data="bly_close")])
    keyboard = InlineKeyboardMarkup(keyboard_buttons)

    response_text = (
        f"🔗 **Bly.to Short Link Generated!**\n\n"
        f"• **Original:** `{long_url}`\n"
        f"• **Shortened:** `{short_link}`"
    )
    if slug:
        response_text += f"\n• **Slug:** `{slug}`"

    await msg.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# --- INTERACTIVE CALLBACK ROUTER ---

@app.on_callback_query(filters.regex(r"^bly_close$"))
async def cb_bly_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
