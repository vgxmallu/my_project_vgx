import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config  # Must contain BITLY_TOKEN

# --- CONFIGURATION ---
BITLY_BASE = "https://api-ssl.bitly.com/v4"

def get_bitly_token() -> str:
    """Retrieves the Bitly Access Token from config safely."""
    return getattr(Config, "BITLY_TOKEN", None)


# --- BITLY API HELPER ---

async def shorten_url_via_bitly(long_url: str) -> str:
    """Sends a POST request to Bitly v4 API to shorten a long URL."""
    token = get_bitly_token()
    if not token:
        return None

    endpoint = f"{BITLY_BASE}/shorten"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {"long_url": long_url.strip()}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(endpoint, json=payload, headers=headers, timeout=15.0)
            if resp.status_code in [200, 201]:
                data = resp.json()
                return data.get("link")
            print(f"Bitly API Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"Bitly API Exception: {e}")
        return None


# --- COMMAND HANDLER ---

@app.on_message(filters.command(["shorten", "bitly", "short"]))
async def cmd_shorten_url(client: Client, message: Message):
    """Command: /shorten <url> - Shortens a long URL using Bitly API."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/shorten https://example.com/very-long-url`\n\n"
            "_Please provide a valid URL to shorten._",
            parse_mode=ParseMode.MARKDOWN
        )

    long_url = args[1].strip()
    
    # Ensure URL has a scheme
    if not long_url.startswith(("http://", "https://")):
        long_url = "https://" + long_url

    msg = await message.reply_text("🔗 Generating short link via Bitly...")

    short_link = await shorten_url_via_bitly(long_url)
    if not short_link:
        return await msg.edit_text("❌ Failed to shorten URL. Check your `BITLY_TOKEN` in `config.py` or ensure the URL is valid.")

    # Inline keyboard action button
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Open Short Link", url=short_link)],
        [InlineKeyboardButton("❌ Close", callback_data="bitly_close")]
    ])

    await msg.edit_text(
        f"🔗 **URL Shortened Successfully!**\n\n"
        f"• **Original:** `{long_url}`\n"
        f"• **Shortened:** `{short_link}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


# --- INTERACTIVE CALLBACK ROUTER ---

@app.on_callback_query(filters.regex(r"^bitly_close$"))
async def cb_bitly_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
