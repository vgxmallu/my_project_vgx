import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config  # Must contain SPOO_API_KEY

# --- CONFIGURATION & BASE URL ---
SPOO_BASE = "https://spoo.me/api/v1"

def get_spoome_token() -> str:
    """Retrieves the Spoo.me API Key from config safely."""
    return getattr(Config, "SPOO_API_KEY", None)


async def spoome_request(method: str, endpoint: str, **kwargs) -> httpx.Response:
    """Centralized HTTP request helper for Spoo.me API using Bearer Token authentication."""
    token = get_spoome_token()
    if not token:
        return None

    url = f"{SPOO_BASE}/{endpoint.lstrip('/')}"
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    headers["Accept"] = "application/json"
    if "json" in kwargs:
        headers["Content-Type"] = "application/json"

    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            m = method.upper()
            if m == "POST":
                return await client.post(url, headers=headers, **kwargs)
            elif m == "GET":
                return await client.get(url, headers=headers, **kwargs)
            elif m == "PUT" or m == "PATCH":
                return await client.patch(url, headers=headers, **kwargs)
            elif m == "DELETE":
                return await client.delete(url, headers=headers, **kwargs)
        except Exception as e:
            print(f"Spoo.me API Exception [{endpoint}]: {e}")
        return None


# ==========================================
# --- SPOO.ME DASHBOARD MENU BUILDER ---
# ==========================================

def get_spoome_main_menu():
    """Interactive dashboard built with Inline Keyboards."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔗 Shorten Link", callback_data="spoo_menu_shorten"),
            InlineKeyboardButton("📋 Manage Links", callback_data="spoo_menu_list")
        ],
        [
            InlineKeyboardButton("📊 Link Stats", callback_data="spoo_menu_stats"),
            InlineKeyboardButton("❌ Close Menu", callback_data="spoo_close")
        ]
    ])


@app.on_message(filters.command(["spoo", "spoome", "spoobot"]))
async def cmd_spoome_main(client: Client, message: Message):
    """Command: /spoo - Opens the Spoo.me link intelligence suite dashboard."""
    text = (
        "🔗 **Spoo.me Link Management & Analytics Suite**\n\n"
        "Welcome! Shorten links with custom slugs/emojis, apply password protection, limit max clicks, and track analytics using the interactive buttons below:"
    )
    await message.reply_text(text, reply_markup=get_spoome_main_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- 1. SHORTENING & CUSTOMIZATION ---
# ==========================================

@app.on_message(filters.command(["spooshort", "spoo_shorten"]))
async def cmd_spoo_shorten(client: Client, message: Message):
    """Command: /spooshort <url> [alias/emoji] [password] [max_clicks]"""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/spooshort <url> [alias/emoji] [password] [max_clicks]`\n\n"
            "_Example:_ `/spooshort https://example.com my-alias Secret123@ 100`",
            parse_mode=ParseMode.MARKDOWN
        )

    long_url = args[1].strip()
    alias = args[2].strip() if len(args) > 2 else None
    password = args[3].strip() if len(args) > 3 else None
    max_clicks = int(args[4]) if len(args) > 4 and args[4].isdigit() else None

    if not long_url.startswith(("http://", "https://")):
        long_url = "https://" + long_url

    msg = await message.reply_text("🚀 Processing link via Spoo.me API...")

    payload = {"long_url": long_url}
    if alias:
        payload["alias"] = alias
    if password:
        payload["password"] = password
    if max_clicks:
        payload["max_clicks"] = max_clicks

    resp = await spoome_request("POST", "links", json=payload, timeout=15.0)
    if not resp or resp.status_code not in [200, 201]:
        err_text = resp.text if resp else "Connection error"
        return await msg.edit_text(f"❌ Failed to shorten link: `{err_text}`", parse_mode=ParseMode.MARKDOWN)

    data = resp.json()
    short_url = data.get("short_url") or data.get("link")
    qr_url = data.get("qr_code_url")

    keyboard_buttons = [[InlineKeyboardButton("🌐 Open Short Link", url=short_url)]]
    if qr_url:
        keyboard_buttons.append([InlineKeyboardButton("📱 View QR Code", url=qr_url)])
    keyboard_buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data="spoo_home")])
    keyboard = InlineKeyboardMarkup(keyboard_buttons)

    await msg.edit_text(
        f"✅ **Spoo.me Short Link Created!**\n\n"
        f"• **Original:** `{long_url}`\n"
        f"• **Shortened:** `{short_url}`\n"
        f"• **Custom Alias/Emoji:** `{alias or 'None'}`\n"
        f"• **Password Protected:** `{'Yes' if password else 'No'}`\n"
        f"• **Max Clicks Limit:** `{max_clicks or 'Unlimited'}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


# ==========================================
# --- 2. ANALYTICS & STATISTICS ---
# ==========================================

@app.on_message(filters.command(["spoostats", "spoo_stats"]))
async def cmd_spoo_stats(client: Client, message: Message):
    """Command: /spoostats <alias_or_id> - Fetches link traffic metrics and bot tracking stats."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/spoostats <short_alias>`", parse_mode=ParseMode.MARKDOWN)

    identifier = args[1].strip()
    msg = await message.reply_text("📊 Fetching link traffic analytics...")

    resp = await spoome_request("GET", f"links/{identifier}/stats", timeout=15.0)
    if not resp or resp.status_code != 200:
        return await msg.edit_text("❌ Failed to fetch statistics. Verify link identifier or API key.")

    stats = resp.json()
    total_clicks = stats.get("total_clicks", 0)
    unique_clicks = stats.get("unique_clicks", 0)
    created_at = stats.get("created_at", "N/A")
    original_url = stats.get("long_url", "N/A")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh Stats", callback_data=f"spoo_refresh_stats_{identifier}")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="spoo_home")]
    ])

    await msg.edit_text(
        f"📊 **Spoo.me Analytics Dashboard**\n\n"
        f"• **Target Link:** `{original_url}`\n"
        f"• **Created On:** `{created_at}`\n"
        f"• **Total Clicks:** `{total_clicks}`\n"
        f"• **Unique Visitors:** `{unique_clicks}`\n"
        f"• **Bot & Client Tracking:** Active 🤖",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


# ==========================================
# --- 3. LINK MANAGEMENT & CRUD OPS ---
# ==========================================

@app.on_message(filters.command(["spoolist", "spoo_list"]))
async def cmd_spoo_list(client: Client, message: Message):
    """Command: /spoolist - Lists account links."""
    msg = await message.reply_text("📋 Fetching your link portfolio...")
    resp = await spoome_request("GET", "links", timeout=15.0)

    if not resp or resp.status_code != 200:
        return await msg.edit_text("❌ Failed to retrieve link entries.")

    result = resp.json()
    links = result.get("data", []) if isinstance(result, dict) else result
    if not links:
        return await msg.edit_text("📭 No active links found in your Spoo.me account.")

    text = "📋 **Your Spoo.me Links (Recent):**\n\n"
    for item in links[:10]:
        s_url = item.get("short_url") or item.get("alias")
        l_url = item.get("long_url", "")
        clicks = item.get("total_clicks", 0)
        text += f"• `{s_url}` (Clicks: {clicks})\n  ↳ __{l_url[:40]}__\n\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh List", callback_data="spoo_menu_list")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="spoo_home")]
    ])
    await msg.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["spooupdate", "spoo_update"]))
async def cmd_spoo_update(client: Client, message: Message):
    """Command: /spooupdate <id> <new_long_url>"""
    args = message.command
    if len(args) < 3:
        return await message.reply_text("⚠️ **Usage:** `/spooupdate <link_id> <new_destination_url>`", parse_mode=ParseMode.MARKDOWN)

    link_id = args[1].strip()
    new_url = args[2].strip()
    msg = await message.reply_text("🔄 Updating link destination...")

    payload = {"long_url": new_url}
    resp = await spoome_request("PATCH", f"links/{link_id}", json=payload, timeout=15.0)

    if not resp or resp.status_code not in [200, 204]:
        return await msg.edit_text("❌ Failed to update link target.")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="spoo_home")]])
    await msg.edit_text(f"✅ Link `{link_id}` successfully updated to target `{new_url}`!", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["spoodelete", "spoo_delete"]))
async def cmd_spoo_delete(client: Client, message: Message):
    """Command: /spoodelete <id>"""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/spoodelete <link_id>`", parse_mode=ParseMode.MARKDOWN)

    link_id = args[1].strip()
    msg = await message.reply_text("🗑️ Deleting short link...")

    resp = await spoome_request("DELETE", f"links/{link_id}", timeout=15.0)
    if not resp or resp.status_code not in [200, 204]:
        return await msg.edit_text("❌ Failed to delete short link.")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="spoo_home")]])
    await msg.edit_text(f"🗑️ Link `{link_id}` has been deleted successfully.", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^spoo_home$"))
async def cb_spoo_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🔗 **Spoo.me Link Management & Analytics Suite**\n\n"
        "Welcome back to the dashboard! Select an option below:"
    )
    await query.message.edit_text(text, reply_markup=get_spoome_main_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^spoo_menu_shorten$"))
async def cb_spoo_menu_shorten(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="spoo_home")]])
    await query.message.edit_text(
        "🚀 **How to Shorten via Chat:**\n\n"
        "Send the command:\n`/spooshort https://example.com my-alias password123 50`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^spoo_menu_list$"))
async def cb_spoo_menu_list(client: Client, query: CallbackQuery):
    await query.answer("Fetching links...")
    resp = await spoome_request("GET", "links", timeout=15.0)
    
    if not resp or resp.status_code != 200:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="spoo_home")]])
        return await query.message.edit_text("❌ Failed to load link list.", reply_markup=keyboard)

    result = resp.json()
    links = result.get("data", []) if isinstance(result, dict) else result
    
    text = "📋 **Your Spoo.me Links Portfolio:**\n\n"
    for item in links[:10]:
        s_url = item.get("short_url") or item.get("alias")
        clicks = item.get("total_clicks", 0)
        text += f"• `{s_url}` — Clicks: `{clicks}`\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="spoo_menu_list")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="spoo_home")]
    ])
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^spoo_menu_stats$"))
async def cb_spoo_menu_stats(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="spoo_home")]])
    await query.message.edit_text(
        "📊 **How to Check Stats:**\n\n"
        "Send the command:\n`/spoostats <short_alias_or_id>`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^spoo_close$"))
async def cb_spoo_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
