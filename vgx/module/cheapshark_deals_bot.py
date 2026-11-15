import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app

# --- CONFIGURATION ---
CHEAPSHARK_BASE = "https://www.cheapshark.com/api/1.0"
PAGE_SIZE = 5  # Deals displayed per page in Telegram UI


def safe_truncate(text: str, max_length: int = 3800) -> str:
    """Safely truncates text to stay well within Telegram's 4000 character limit."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n\n... _(Output truncated due to length limitations)_"


async def cheapshark_request(endpoint: str, params: dict = None) -> dict:
    """Helper utility for asynchronous requests to the CheapShark API."""
    url = f"{CHEAPSHARK_BASE.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {
        "User-Agent": "TelegramBot-CheapSharkSuite/1.0 (Contact: admin@bot.com)",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        try:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                return {"success": True, "data": resp.json()}
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:300]}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ==========================================
# --- UI BUILDERS (100% CALLBACK BUTTONS) ---
# ==========================================

def build_home_keyboard() -> InlineKeyboardMarkup:
    """Master dashboard keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔥 Top Game Deals", callback_data="cs_deals_0"),
            InlineKeyboardButton("🏪 Store List", callback_data="cs_stores"),
        ],
        [
            InlineKeyboardButton("🔍 Search Game Lookup", callback_data="cs_search_help"),
            InlineKeyboardButton("❌ Close", callback_data="cs_close"),
        ],
    ])


def build_deals_keyboard(page: int, has_next: bool, items_len: int) -> InlineKeyboardMarkup:
    """Pagination and deal navigation keyboard."""
    buttons = []

    # Deal inspector trigger buttons (row of numbers matching items on screen)
    inspect_row = []
    for i in range(min(items_len, PAGE_SIZE)):
        inspect_row.append(InlineKeyboardButton(f"#{i + 1}", callback_data=f"cs_deal_inspect_{page}_{i}"))
    if inspect_row:
        buttons.append(inspect_row)

    # Pagination controls
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⏮️ First", callback_data="cs_deals_0"))
        nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"cs_deals_{page - 1}"))
    nav_row.append(InlineKeyboardButton(f"📄 Page {page + 1}", callback_data=f"cs_deals_{page}"))
    if has_next:
        nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"cs_deals_{page + 1}"))
    buttons.append(nav_row)

    # Footer controls
    buttons.append([
        InlineKeyboardButton("🔄 Refresh", callback_data=f"cs_deals_{page}"),
        InlineKeyboardButton("🏠 Home", callback_data="cs_home"),
        InlineKeyboardButton("❌ Close", callback_data="cs_close"),
    ])
    return InlineKeyboardMarkup(buttons)


# ==========================================
# --- COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.command(["cheapshark", "deals", "gamedeals", "pcdeals"]))
async def cmd_cheapshark_dashboard(client: Client, message: Message):
    """Command: /deals - Opens the CheapShark PC Game Price Comparison Suite."""
    text = (
        "🦈 **CheapShark PC Game Deals Suite**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Compare prices across Steam, Fanatical, GreenManGaming, and top digital storefronts instantly.\n\n"
        "👉 **Quick Commands:**\n"
        "• `/deals` — Browse top discounts\n"
        "• `/searchgame <title>` — Search for specific game prices\n"
        "• `/stores` — View active PC stores"
    )
    await message.reply_text(
        safe_truncate(text),
        reply_markup=build_home_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.command(["searchgame", "findgame"]))
async def cmd_search_game(client: Client, message: Message):
    """Command: /searchgame <title> - Looks up game pricing across stores."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/searchgame Witcher 3`",
            parse_mode=ParseMode.MARKDOWN,
        )

    query_str = " ".join(args[1:])
    msg = await message.reply_text(f"🔍 Searching CheapShark for `{query_str}`...")

    res = await cheapshark_request("games", params={"title": query_str, "limit": 6})
    if not res["success"]:
        return await msg.edit_text(f"❌ **Error:** `{res['error']}`", parse_mode=ParseMode.MARKDOWN)

    games = res["data"]
    if not games:
        return await msg.edit_text(f"📭 No games found matching `{query_str}`.")

    output = [f"🔍 **SEARCH RESULTS: `{query_str}`**\n━━━━━━━━━━━━━━━━━━━━━━"]
    buttons = []

    for idx, g in enumerate(games[:5]):
        name = g.get("external", "Unknown Title")
        cheapest = g.get("cheapest", "N/A")
        game_id = g.get("gameID")
        thumb = g.get("thumb", "")

        output.append(f"• **{name}**\n   └ 🏷️ Best Price: `${cheapest}` (ID: `{game_id}`)")
        buttons.append([InlineKeyboardButton(f"📦 View Deals: {name[:20]}", callback_data=f"cs_gameid_{game_id}")])

    buttons.append([InlineKeyboardButton("🏠 Home", callback_data="cs_home"), InlineKeyboardButton("❌ Close", callback_data="cs_close")])
    keyboard = InlineKeyboardMarkup(buttons)

    await msg.edit_text(
        safe_truncate("\n".join(output)),
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.command(["stores", "pcstores"]))
async def cmd_list_stores(client: Client, message: Message):
    """Command: /stores - Lists active digital storefronts tracked by CheapShark."""
    msg = await message.reply_text("🏪 Fetching active store list...")
    res = await cheapshark_request("stores")

    if not res["success"]:
        return await msg.edit_text(f"❌ **Error:** `{res['error']}`")

    stores = res["data"]
    output = [f"🏪 **ACTIVE DIGITAL STORES ({len(stores)})**\n━━━━━━━━━━━━━━━━━━━━━━"]
    for s in stores:
        if s.get("isActive") == 1:
            name = s.get("storeName")
            sid = s.get("storeID")
            output.append(f"• **{name}** (Store ID: `{sid}`)")

    output.append("━━━━━━━━━━━━━━━━━━━━━━")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="cs_home"), InlineKeyboardButton("❌ Close", callback_data="cs_close")]])
    await msg.edit_text(safe_truncate("\n".join(output)), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- CALLBACK CONTROLLERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^cs_home$"))
async def cb_cheapshark_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🦈 **CheapShark PC Game Deals Suite**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Compare prices across Steam, Fanatical, GreenManGaming, and top digital storefronts instantly."
    )
    if query.message.photo:
        await query.message.delete()
        await query.message.reply_text(safe_truncate(text), reply_markup=build_home_keyboard(), parse_mode=ParseMode.MARKDOWN)
    else:
        await query.message.edit_text(safe_truncate(text), reply_markup=build_home_keyboard(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^cs_deals_(?P<page>\d+)$"))
async def cb_cheapshark_deals(client: Client, query: CallbackQuery):
    page = int(query.matches[0].group("page"))
    await query.answer(f"Loading deals page {page + 1}...")

    res = await cheapshark_request("deals", params={"pageNumber": page, "pageSize": PAGE_SIZE, "sortBy": "DealRating"})
    if not res["success"]:
        return await query.answer(f"Error: {res['error'][:150]}", show_alert=True)

    items = res["data"]
    has_next = len(items) == PAGE_SIZE

    lines = [
        f"🔥 **TOP PC GAME DEALS (Page {page + 1})**",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for idx, d in enumerate(items[:PAGE_SIZE]):
        title = d.get("title", "Unknown Game")
        sale_price = d.get("salePrice", "0")
        normal_price = d.get("normalPrice", "0")
        savings = float(d.get("savings", "0"))
        rating = d.get("dealRating", "0")

        lines.append(
            f"**{idx + 1}. {title}**\n"
            f"   💰 **${sale_price}** ~~(${normal_price})~~ | 📉 **-{savings:.1f}%** | ⭐ Rating: `{rating}`"
        )

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("👇 _Tap deal number buttons below to view full details._")

    keyboard = build_deals_keyboard(page, has_next, len(items))

    if query.message.photo:
        await query.message.delete()
        await query.message.reply_text(safe_truncate("\n".join(lines)), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    else:
        await query.message.edit_text(safe_truncate("\n".join(lines)), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^cs_deal_inspect_(?P<page>\d+)_(?P<idx>\d+)$"))
async def cb_cheapshark_inspect_deal(client: Client, query: CallbackQuery):
    page = int(query.matches[0].group("page"))
    idx = int(query.matches[0].group("idx"))
    await query.answer("Fetching deal details & artwork...")

    res = await cheapshark_request("deals", params={"pageNumber": page, "pageSize": PAGE_SIZE, "sortBy": "DealRating"})
    back_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔙 Back to Deals", callback_data=f"cs_deals_{page}"),
            InlineKeyboardButton("🏠 Home", callback_data="cs_home"),
        ],
        [InlineKeyboardButton("❌ Close", callback_data="cs_close")],
    ])

    if not res["success"] or idx >= len(res["data"]):
        return await query.answer("Deal data expired or not found.", show_alert=True)

    deal = res["data"][idx]
    title = deal.get("title", "Unknown")
    sale = deal.get("salePrice")
    normal = deal.get("normalPrice")
    savings = float(deal.get("savings", "0"))
    rating = deal.get("dealRating")
    metacritic = deal.get("metacriticScore", "N/A")
    steam_rating = deal.get("steamRatingPercent", "N/A")
    thumb = deal.get("thumb")

    caption = (
        f"🎮 **DEAL DETAILS — {title}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• 💰 **Sale Price:** `${sale}` (Regular: `${normal}`)\n"
        f"• 📉 **Discount:** `{savings:.1f}% OFF`\n"
        f"• ⭐ **Deal Rating Score:** `{rating} / 10`\n"
        f"• 🖥️ **Metacritic Score:** `{metacritic}`\n"
        f"• 💨 **Steam Reviews:** `{steam_rating}%`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• 🔗 _Use /searchgame to look up direct price comparisons across stores._"
    )

    if thumb:
        try:
            await query.message.delete()
            await query.message.reply_photo(
                photo=thumb,
                caption=safe_truncate(caption),
                reply_markup=back_kb,
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        except Exception:
            pass

    await query.message.edit_text(
        safe_truncate(caption),
        reply_markup=back_kb,
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_callback_query(filters.regex(r"^cs_gameid_(?Pgameid>.+)$"))
async def cb_cheapshark_game_lookup(client: Client, query: CallbackQuery):
    game_id = query.matches[0].group("gameid")
    await query.answer("Fetching multi-store price comparison...")

    res = await cheapshark_request("games", params={"id": game_id})
    back_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Home", callback_data="cs_home"), InlineKeyboardButton("❌ Close", callback_data="cs_close")]
    ])

    if not res["success"]:
        return await query.answer("Could not load game pricing info.", show_alert=True)

    data = res["data"]
    info = data.get("info", {})
    deals = data.get("deals", [])

    title = info.get("name", "Unknown Game")
    thumb = info.get("thumb")

    lines = [
        f"🏷️ **STORE PRICES FOR: {title}**",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for d in deals[:6]:
        price = d.get("price")
        retail = d.get("retailPrice")
        # Map store ID roughly or display store ID
        sid = d.get("storeID")
        lines.append(f"• **Store ID #{sid}** — 💰 **${price}** ~~(${retail})~~")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    caption = "\n".join(lines)

    if thumb:
        try:
            await query.message.delete()
            await query.message.reply_photo(
                photo=thumb,
                caption=safe_truncate(caption),
                reply_markup=back_kb,
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        except Exception:
            pass

    await query.message.edit_text(
        safe_truncate(caption),
        reply_markup=back_kb,
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_callback_query(filters.regex(r"^cs_stores$"))
async def cb_cheapshark_stores_menu(client: Client, query: CallbackQuery):
    await query.answer("Fetching stores...")
    res = await cheapshark_request("stores")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Home", callback_data="cs_home"), InlineKeyboardButton("❌ Close", callback_data="cs_close")]
    ])

    if not res["success"]:
        return await query.answer("Failed to fetch stores.", show_alert=True)

    stores = res["data"]
    output = [f"🏪 **ACTIVE DIGITAL STORES ({len(stores)})**\n━━━━━━━━━━━━━━━━━━━━━━"]
    for s in stores:
        if s.get("isActive") == 1:
            output.append(f"• **{s.get('storeName')}** (ID: `{s.get('storeID')}`)")

    output.append("━━━━━━━━━━━━━━━━━━━━━━")
    if query.message.photo:
        await query.message.delete()
        await query.message.reply_text(safe_truncate("\n".join(output)), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else:
        await query.message.edit_text(safe_truncate("\n".join(output)), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^cs_search_help$"))
async def cb_cheapshark_search_help(client: Client, query: CallbackQuery):
    await query.answer()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Home", callback_data="cs_home"), InlineKeyboardButton("❌ Close", callback_data="cs_close")]
    ])
    text = (
        "🔍 **How to Search Game Prices:**\n\n"
        "Send the following command in chat:\n"
        "`/searchgame <Game Title>`\n\n"
        "_Example:_ `/searchgame Cyberpunk 2077`\n\n"
        "You can inspect prices across all tracked stores instantly!"
    )
    if query.message.photo:
        await query.message.delete()
        await query.message.reply_photo(photo="https://www.cheapshark.com/img/logo.png", caption=safe_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else:
        await query.message.edit_text(safe_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^cs_close$"))
async def cb_cheapshark_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
