import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config  # Must contain TLY_TOKEN

# --- CONFIGURATION & BASE URL ---
TLY_BASE = "https://api.t.ly/api/v1"

def get_tly_token() -> str:
    """Retrieves the T.LY API Token from config safely."""
    return getattr(Config, "TLY_TOKEN", None)


async def tly_request(method: str, endpoint: str, **kwargs) -> httpx.Response:
    """Centralized HTTP request helper for T.LY endpoints using Bearer token authentication."""
    token = get_tly_token()
    if not token:
        return None

    url = f"{TLY_BASE}/{endpoint.lstrip('/')}"
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    headers["Accept"] = "application/json"

    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            if method.upper() == "POST":
                return await client.post(url, headers=headers, **kwargs)
            elif method.upper() == "GET":
                return await client.get(url, headers=headers, **kwargs)
        except Exception as e:
            print(f"T.LY API Exception [{endpoint}]: {e}")
        return None


# ==========================================
# --- T.LY DASHBOARD MENU BUILDER ---
# ==========================================

def get_tly_main_menu():
    """Main interactive menu built entirely with Inline Keyboards."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔗 Shorten Link", callback_data="tly_menu_shorten"),
            InlineKeyboardButton("📖 Expand Link", callback_data="tly_menu_expand")
        ],
        [
            InlineKeyboardButton("📋 List Links", callback_data="tly_menu_list"),
            InlineKeyboardButton("📊 Link Stats", callback_data="tly_menu_stats")
        ],
        [
            InlineKeyboardButton("❌ Close Menu", callback_data="tly_close")
        ]
    ])


@app.on_message(filters.command(["tly", "tlybot", "tlyhub"]))
async def cmd_tly_main(client: Client, message: Message):
    """Command: /tly - Opens the interactive T.LY management dashboard."""
    text = (
        "🟢 **T.LY URL Shortener & Analytics Suite**\n\n"
        "Welcome! Manage your short URLs, expand links, view QR codes, and check click stats using the interactive buttons below:"
    )
    await message.reply_text(text, reply_markup=get_tly_main_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- FEATURE COMMANDS & CALLBACKS ---
# ==========================================

# 1. Shorten Link Handler
@app.on_message(filters.command(["tlyshort", "tly_shorten"]))
async def cmd_tly_shorten(client: Client, message: Message):
    """Command: /tlyshort <url> - Shortens a long URL via T.LY."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/tlyshort https://example.com/very-long-url`",
            parse_mode=ParseMode.MARKDOWN
        )

    long_url = args[1].strip()
    if not long_url.startswith(("http://", "https://")):
        long_url = "https://" + long_url

    msg = await message.reply_text("🔗 Creating short link on T.LY...")

    payload = {
        "long_url": long_url,
        "include_qr_code": True
    }
    resp = await tly_request("POST", "link/shorten", json=payload, timeout=15.0)

    if not resp or resp.status_code not in [200, 201]:
        return await msg.edit_text("❌ Failed to shorten URL. Verify your `TLY_TOKEN` in `config.py`.")

    data = resp.json()
    short_url = data.get("short_url")
    qr_code_url = data.get("qr_code_url")

    keyboard_buttons = [[InlineKeyboardButton("🌐 Open Short Link", url=short_url)]]
    if qr_code_url:
        keyboard_buttons.append([InlineKeyboardButton("📱 View QR Code", url=qr_code_url)])
    keyboard_buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data="tly_home")])
    keyboard = InlineKeyboardMarkup(keyboard_buttons)

    await msg.edit_text(
        f"✅ **T.LY Short Link Created Successfully!**\n\n"
        f"• **Original:** `{long_url}`\n"
        f"• **Shortened:** `{short_url}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


# 2. Expand Link Handler
@app.on_message(filters.command(["tlyexpand", "tly_expand"]))
async def cmd_tly_expand(client: Client, message: Message):
    """Command: /tlyexpand <short_url> - Retrieves original long URL."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/tlyexpand https://t.ly/xxxx`",
            parse_mode=ParseMode.MARKDOWN
        )

    short_url = args[1].strip()
    msg = await message.reply_text("📖 Expanding T.LY short link...")

    payload = {"short_url": short_url, "is_qr_code": False}
    resp = await tly_request("POST", "link/expand", json=payload, timeout=15.0)

    if not resp or resp.status_code != 200:
        return await msg.edit_text("❌ Failed to expand link. Make sure the short URL is valid and belongs to your account.")

    data = resp.json()
    long_url = data.get("long_url", "Unknown destination")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Open Destination", url=long_url)],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="tly_home")]
    ])

    await msg.edit_text(
        f"📖 **Link Expander Results**\n\n"
        f"• **Short URL:** `{short_url}`\n"
        f"• **Long URL:** `{long_url}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


# 3. List Links Handler
@app.on_message(filters.command(["tlylist", "tly_list"]))
async def cmd_tly_list(client: Client, message: Message):
    """Command: /tlylist - Displays recent short links."""
    msg = await message.reply_text("📋 Fetching your recent T.LY links...")
    resp = await tly_request("GET", "link/list", timeout=15.0)

    if not resp or resp.status_code != 200:
        return await msg.edit_text("❌ Failed to fetch link records.")

    result = resp.json()
    links = result.get("data", []) if isinstance(result, dict) else result
    if not links:
        return await msg.edit_text("📭 No short links found in your account.")

    text = "📋 **Your Recent T.LY Links:**\n\n"
    for item in links[:10]:  # Show top 10 recent links
        s_url = item.get("short_url")
        l_url = item.get("long_url")
        text.append(f"• [{s_url}]({s_url}) ➡️ `{l_url[:40]}...`\n")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh List", callback_data="tly_menu_list")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="tly_home")]
    ])
    await msg.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^tly_home$"))
async def cb_tly_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🟢 **T.LY URL Shortener & Analytics Suite**\n\n"
        "Welcome back to the main dashboard! Select an option below:"
    )
    await query.message.edit_text(text, reply_markup=get_tly_main_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^tly_menu_shorten$"))
async def cb_tly_menu_shorten(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="tly_home")]])
    await query.message.edit_text(
        "🔗 **How to Shorten a Link:**\n\n"
        "Send the following command in chat:\n`/tlyshort https://example.com`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^tly_menu_expand$"))
async def cb_tly_menu_expand(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="tly_home")]])
    await query.message.edit_text(
        "📖 **How to Expand a Link:**\n\n"
        "Send the following command in chat:\n`/tlyexpand https://t.ly/xxxx`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^tly_menu_list$"))
async def cb_tly_menu_list(client: Client, query: CallbackQuery):
    await query.answer("Fetching links...")
    resp = await tly_request("GET", "link/list", timeout=15.0)
    
    if not resp or resp.status_code != 200:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="tly_home")]])
        return await query.message.edit_text("❌ Failed to fetch links.", reply_markup=keyboard)

    result = resp.json()
    links = result.get("data", []) if isinstance(result, dict) else result
    
    text = "📋 **Your Recent T.LY Links (Top 10):**\n\n"
    for item in links[:10]:
        s_url = item.get("short_url")
        l_url = item.get("long_url", "")
        text += f"• `{s_url}`\n  ↳ __{l_url[:50]}__\n\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="tly_menu_list")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="tly_home")]
    ])
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^tly_menu_stats$"))
async def cb_tly_menu_stats(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="tly_home")]])
    await query.message.edit_text(
        "📊 **Link Click Analytics:**\n\n"
        "To check stats for a short link, use:\n`/tlystats https://t.ly/xxxx`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^tly_close$"))
async def cb_tly_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
