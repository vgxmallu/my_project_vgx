import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config  # Must contain BITLY_CLIENT_ID & BITLY_CLIENT_SECRET

# --- CONFIGURATION & ENDPOINTS ---
AUTH_URL = "https://bitly.com/oauth/authorize"
TOKEN_URL = "https://api-ssl.bitly.com/oauth/access_token"
API_BASE = "https://api-ssl.bitly.com/v4"

# In-memory session store for runtime tokens (can be replaced with MongoDB if needed)
SESSION_TOKENS = {}

def get_client_credentials() -> tuple:
    """Retrieves Client ID, Client Secret, and Redirect URI from config safely."""
    client_id = getattr(Config, "BITLY_CLIENT_ID", None)
    client_secret = getattr(Config, "BITLY_CLIENT_SECRET", None)
    redirect_uri = getattr(Config, "BITLY_REDIRECT_URI", "http://localhost/")
    return client_id, client_secret, redirect_uri


# --- OAUTH & API HELPERS ---

async def exchange_code_for_token(code: str) -> str:
    """Exchanges Bitly OAuth authorization code for an access token using Client ID & Secret."""
    client_id, client_secret, redirect_uri = get_client_credentials()
    if not client_id or not client_secret:
        return None

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code.strip(),
        "redirect_uri": redirect_uri
    }
    headers = {"Accept": "application/json"}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(TOKEN_URL, data=payload, headers=headers, timeout=15.0)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("access_token")
            print(f"Bitly Token Exchange Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"Bitly Token Exchange Exception: {e}")
        return None


async def shorten_url(long_url: str, access_token: str) -> str:
    """Shortens a URL using Bitly v4 API with the dynamic OAuth access token."""
    endpoint = f"{API_BASE}/shorten"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {"long_url": long_url.strip()}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(endpoint, json=payload, headers=headers, timeout=15.0)
            if resp.status_code in [200, 201]:
                return resp.json().get("link")
            print(f"Bitly Shorten Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"Bitly Shorten Exception: {e}")
        return None


# --- COMMAND HANDLERS ---

@app.on_message(filters.command(["bitlyauth", "bitlylogin"]))
async def cmd_bitly_auth(client: Client, message: Message):
    """Step 1: Generates the Bitly OAuth Authorization URL using Client ID."""
    client_id, _, redirect_uri = get_client_credentials()
    if not client_id:
        return await message.reply_text("❌ `BITLY_CLIENT_ID` is missing in `config.py`.", parse_mode=ParseMode.MARKDOWN)

    auth_link = f"{AUTH_URL}?client_id={client_id}&redirect_uri={redirect_uri}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Authorize App on Bitly", url=auth_link)],
        [InlineKeyboardButton("❌ Close", callback_data="bitly_auth_close")]
    ])

    await message.reply_text(
        "🔐 **Bitly OAuth Authentication**\n\n"
        "1. Click the button below to log in and authorize your app.\n"
        "2. Bitly will redirect your browser to your `redirect_uri` with a `code=` parameter.\n"
        "3. Copy that code and send it to the bot using:\n`/bitlycode <your_code>`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_message(filters.command(["bitlycode", "bitlyexchange"]))
async def cmd_bitly_exchange(client: Client, message: Message):
    """Step 2: Exchanges the authorization code for an access token."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/bitlycode <authorization_code>`\n\n"
            "_Paste the `code` parameter received from Bitly after authorization._",
            parse_mode=ParseMode.MARKDOWN
        )

    code = args[1].strip()
    msg = await message.reply_text("🔄 Exchanging OAuth code for Bitly access token...")

    access_token = await exchange_code_for_token(code)
    if not access_token:
        return await msg.edit_text("❌ Failed to exchange code. Ensure your `client_secret` and `redirect_uri` match your Bitly app developer settings.")

    # Cache token in memory session for this user
    user_id = message.from_user.id
    SESSION_TOKENS[user_id] = access_token

    await msg.edit_text(
        "✅ **Bitly Authentication Successful!**\n\n"
        "Your OAuth access token has been generated using your app credentials and cached for your session.\n\n"
        "🚀 You can now shorten links using:\n`/shorten https://example.com`",
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_message(filters.command(["shorten", "bitly", "short"]))
async def cmd_shorten(client: Client, message: Message):
    """Step 3: Shortens a URL using the authenticated Bitly session."""
    user_id = message.from_user.id
    token = SESSION_TOKENS.get(user_id)

    if not token:
        return await message.reply_text(
            "⚠️ **Authentication Required!**\n\n"
            "You haven't authenticated your Bitly application yet.\n"
            "Please run `/bitlyauth` first to link your account.",
            parse_mode=ParseMode.MARKDOWN
        )

    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/shorten <url>`", parse_mode=ParseMode.MARKDOWN)

    long_url = args[1].strip()
    if not long_url.startswith(("http://", "https://")):
        long_url = "https://" + long_url

    msg = await message.reply_text("🔗 Generating short link via Bitly API...")

    short_link = await shorten_url(long_url, token)
    if not short_link:
        return await msg.edit_text("❌ Failed to shorten URL. Your session token may have expired. Run `/bitlyauth` again.")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Open Short Link", url=short_link)],
        [InlineKeyboardButton("❌ Close", callback_data="bitly_auth_close")]
    ])

    await msg.edit_text(
        f"🔗 **URL Shortened Successfully!**\n\n"
        f"• **Original:** `{long_url}`\n"
        f"• **Shortened:** `{short_link}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^bitly_auth_close$"))
async def cb_bitly_auth_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
