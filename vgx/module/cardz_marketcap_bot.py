import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app

# --- CONFIGURATION ---
CARDZ_API_BASE = "https://cardzmarketcap.com/api/v1/market"
PAGE_SIZE = 8  # Cards displayed per page in Telegram UI


def safe_truncate(text: str, max_length: int = 3800) -> str:
    """Safely truncates text to stay well within Telegram's 4000 character limit."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n\n... _(Output truncated due to length limitations)_"


def format_currency(val) -> str:
    """Formats numeric USD figures cleanly."""
    if val is None or val == "":
        return "Unverified"
    try:
        num = float(val)
        if num >= 1_000_000_000:
            return f"${num / 1_000_000_000:,.2f}B"
        if num >= 1_000_000:
            return f"${num / 1_000_000:,.2f}M"
        return f"${num:,.2f}"
    except (ValueError, TypeError):
        return str(val)


def format_int(val) -> str:
    """Formats population counts cleanly."""
    if val is None or val == "":
        return "Unverified"
    try:
        return f"{int(val):,}"
    except (ValueError, TypeError):
        return str(val)


async def fetch_cardz_market(scope: str = "pokemon", page: int = 1) -> dict:
    """Fetches paginated PSA 10 market cap rankings from CardZ Marketcap API."""
    params = {"page": page}
    if scope and scope != "all":
        params["scope"] = scope

    headers = {
        "Accept": "application/json",
        "User-Agent": "CardZMarketcap-TelegramSuite/1.0",
    }

    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        try:
            resp = await client.get(CARDZ_API_BASE, params=params, headers=headers)
            if resp.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}: {safe_truncate(resp.text, 400)}",
                }

            payload = resp.json()

            if isinstance(payload, list):
                items = payload
                meta = {}
            else:
                items = (
                    payload.get("items")
                    or payload.get("data")
                    or payload.get("cards")
                    or payload.get("rankings")
                    or []
                )
                meta = payload.get("meta") or payload

            return {
                "success": True,
                "items": items,
                "snapshot_date": meta.get("effective_date") or meta.get("effectiveDate") or meta.get("date") or "Latest Daily Snapshot",
                "generation": meta.get("generation") or meta.get("snapshot_id") or "Daily",
                "total_pages": meta.get("total_pages") or meta.get("totalPages") or 0,
                "total_items": meta.get("total") or meta.get("total_items") or len(items),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# ==========================================
# --- UI BUILDERS (100% CALLBACK BUTTONS) ---
# ==========================================

def build_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Pokémon Market Cap", callback_data="cz_list_pokemon_1"),
            InlineKeyboardButton("🏴‍☠️ One Piece Market Cap", callback_data="cz_list_onepiece_1"),
        ],
        [
            InlineKeyboardButton("🌐 All Ranked Cards", callback_data="cz_list_all_1"),
            InlineKeyboardButton("📐 Index Methodology", callback_data="cz_method"),
        ],
        [
            InlineKeyboardButton("📅 Snapshot Info", callback_data="cz_snapshot"),
            InlineKeyboardButton("❌ Close", callback_data="cz_close"),
        ],
    ])


def build_market_keyboard(scope: str, page: int, items: list, has_next: bool) -> InlineKeyboardMarkup:
    buttons = []

    # Scope Switcher Bar
    buttons.append([
        InlineKeyboardButton(f"{'• ' if scope == 'pokemon' else ''}⚡ Pokémon", callback_data="cz_list_pokemon_1"),
        InlineKeyboardButton(f"{'• ' if scope == 'onepiece' else ''}🏴‍☠️ One Piece", callback_data="cz_list_onepiece_1"),
        InlineKeyboardButton(f"{'• ' if scope == 'all' else ''}🌐 All", callback_data="cz_list_all_1"),
    ])

    # Card Inspector Buttons (with picture preview triggers)
    card_row = []
    for idx, card in enumerate(items[:PAGE_SIZE]):
        rank = card.get("rank") or ((page - 1) * PAGE_SIZE + idx + 1)
        raw_name = card.get("name") or card.get("card_name") or card.get("title") or f"Card #{rank}"
        short_label = f"#{rank} {raw_name[:15]}"
        card_row.append(
            InlineKeyboardButton(short_label, callback_data=f"cz_card_{scope}_{page}_{idx}")
        )
        if len(card_row) == 2:
            buttons.append(card_row)
            card_row = []
    if card_row:
        buttons.append(card_row)

    # Pagination
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⏮️ First", callback_data=f"cz_list_{scope}_1"))
        nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"cz_list_{scope}_{page - 1}"))
    nav_row.append(InlineKeyboardButton(f"📄 Page {page}", callback_data=f"cz_list_{scope}_{page}"))
    if has_next:
        nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"cz_list_{scope}_{page + 1}"))
    buttons.append(nav_row)

    # Footer
    buttons.append([
        InlineKeyboardButton("🔄 Refresh", callback_data=f"cz_list_{scope}_{page}"),
        InlineKeyboardButton("🏠 Home", callback_data="cz_home"),
        InlineKeyboardButton("❌ Close", callback_data="cz_close"),
    ])

    return InlineKeyboardMarkup(buttons)


def format_market_page(scope: str, page: int, res: dict) -> str:
    scope_titles = {
        "pokemon": "⚡ POKÉMON PSA 10 MARKET CAP",
        "onepiece": "🏴‍☠️ ONE PIECE PSA 10 MARKET CAP",
        "all": "🌐 GLOBAL TCG PSA 10 MARKET CAP",
    }
    header = scope_titles.get(scope, "🃏 CARDZ MARKETCAP RANKINGS")
    items = res["items"][:PAGE_SIZE]

    lines = [
        f"**{header}**",
        f"📅 _Snapshot:_ `{res['snapshot_date']}` | 📄 _Page:_ `{page}`",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if not items:
        lines.append("📭 _No ranked cards returned for this page/scope._")
    else:
        for idx, card in enumerate(items):
            rank = card.get("rank") or ((page - 1) * PAGE_SIZE + idx + 1)
            name = card.get("name") or card.get("card_name") or card.get("title") or "Unknown Card"
            set_name = card.get("set_name") or card.get("set") or ""
            lang = card.get("language") or card.get("lang") or ""
            mcap = format_currency(card.get("market_cap") or card.get("marketCap"))
            price = format_currency(card.get("price") or card.get("reference_price") or card.get("psa10_price"))
            pop = format_int(card.get("population") or card.get("psa10_population") or card.get("pop"))

            tag_str = f" `[{lang.upper()}]`" if lang else ""
            set_str = f" — _{set_name}_" if set_name else ""
            lines.append(
                f"**#{rank} {name}**{tag_str}{set_str}\n"
                f"   💎 **MCap:** `{mcap}` | 💵 **PSA 10:** `{price}` | 👥 **Pop:** `{pop}`"
            )

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("👇 _Tap any card button below to inspect full metrics & view card artwork picture._")
    return "\n".join(lines)


# ==========================================
# --- ENTRY COMMAND ---
# ==========================================

@app.on_message(filters.command(["cardz", "cardzmarket", "psa10", "tcgcap"]))
async def cmd_cardz_dashboard(client: Client, message: Message):
    text = (
        "🃏 **CardZ Marketcap Intelligence Suite**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Daily PSA 10 market capitalization index for graded **Pokémon** and **One Piece** trading cards with visual artwork previews.\n\n"
        "📐 **Formula:**\n"
        "`Market Cap = PSA 10 Reference Price × Verified PSA 10 Population`\n\n"
        "Select a market index below using the interactive controls:"
    )
    await message.reply_text(
        safe_truncate(text),
        reply_markup=build_home_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


# ==========================================
# --- CALLBACK CONTROLLERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^cz_home$"))
async def cb_cardz_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🃏 **CardZ Marketcap Intelligence Suite**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Daily PSA 10 market capitalization index for graded **Pokémon** and **One Piece** trading cards with visual artwork previews.\n\n"
        "📐 **Formula:**\n"
        "`Market Cap = PSA 10 Reference Price × Verified PSA 10 Population`\n\n"
        "Select a market index below using the interactive controls:"
    )
    await query.message.edit_text(
        safe_truncate(text),
        reply_markup=build_home_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_callback_query(filters.regex(r"^cz_list_(?P<scope>[a-z]+)_(?P<page>\d+)$"))
async def cb_cardz_list(client: Client, query: CallbackQuery):
    scope = query.matches[0].group("scope")
    page = int(query.matches[0].group("page"))
    await query.answer(f"Loading {scope.upper()} page {page}...")

    res = await fetch_cardz_market(scope=scope, page=page)
    if not res["success"]:
        err_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Retry", callback_data=f"cz_list_{scope}_{page}"),
                InlineKeyboardButton("🏠 Home", callback_data="cz_home"),
            ]
        ])
        return await query.message.edit_text(
            f"❌ **API Error:**\n`{res['error']}`",
            reply_markup=err_kb,
            parse_mode=ParseMode.MARKDOWN,
        )

    items = res["items"]
    total_pages = res.get("total_pages", 0)
    has_next = (page < total_pages) if total_pages else (len(items) >= PAGE_SIZE)

    text = format_market_page(scope, page, res)
    keyboard = build_market_keyboard(scope, page, items, has_next)

    # Handle text edit safely if message was previously a photo/media card
    if query.message.photo:
        await query.message.delete()
        await query.message.reply_text(
            safe_truncate(text),
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await query.message.edit_text(
            safe_truncate(text),
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
        )


@app.on_callback_query(filters.regex(r"^cz_card_(?P<scope>[a-z]+)_(?P<page>\d+)_(?P<idx>\d+)$"))
async def cb_cardz_detail(client: Client, query: CallbackQuery):
    scope = query.matches[0].group("scope")
    page = int(query.matches[0].group("page"))
    idx = int(query.matches[0].group("idx"))
    await query.answer("Fetching card picture & printing metrics...")

    res = await fetch_cardz_market(scope=scope, page=page)
    back_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔙 Back to Rankings", callback_data=f"cz_list_{scope}_{page}"),
            InlineKeyboardButton("🏠 Home", callback_data="cz_home"),
        ],
        [InlineKeyboardButton("❌ Close", callback_data="cz_close")],
    ])

    if not res["success"] or idx >= len(res["items"]):
        return await query.message.edit_text(
            "⚠️ Could not load card details for this snapshot.",
            reply_markup=back_kb,
            parse_mode=ParseMode.MARKDOWN,
        )

    card = res["items"][idx]
    rank = card.get("rank") or ((page - 1) * PAGE_SIZE + idx + 1)
    name = card.get("name") or card.get("card_name") or card.get("title") or "Unknown Printing"
    card_num = card.get("number") or card.get("card_number") or "N/A"
    set_name = card.get("set_name") or card.get("set") or "N/A"
    lang = card.get("language") or card.get("lang") or "N/A"
    finish = card.get("finish") or card.get("variant") or "Standard"
    price = format_currency(card.get("price") or card.get("reference_price") or card.get("psa10_price"))
    pop = format_int(card.get("population") or card.get("psa10_population") or card.get("pop"))
    mcap = format_currency(card.get("market_cap") or card.get("marketCap"))
    obs_date = card.get("observed_date") or card.get("updated_at") or res["snapshot_date"]

    # Extract card artwork picture URL from flexible keys
    image_url = (
        card.get("image_url")
        or card.get("imageUrl")
        or card.get("image")
        or card.get("img")
        or card.get("thumbnail")
    )

    caption = (
        f"🎴 **CARD PICTURE & METRICS — RANK #{rank}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• 🏷️ **Card Name:** `{name}`\n"
        f"• 📦 **Set:** `{set_name}`\n"
        f"• 🔢 **Card Number:** `{card_num}`\n"
        f"• 🌐 **Language / Finish:** `{lang}` / `{finish}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• 🏅 **Grading Standard:** `PSA 10 Only`\n"
        f"• 💵 **PSA 10 Reference Price:** `{price}`\n"
        f"• 👥 **Verified PSA 10 Population:** `{pop}`\n"
        f"• 💎 **Calculated Market Cap:** `{mcap}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• 📅 **Snapshot Effective Date:** `{res['snapshot_date']}`\n"
        f"• 🕒 **Observation Date:** `{obs_date}`"
    )

    # If image URL exists, send as an official Telegram photo card preview
    if image_url:
        try:
            await query.message.delete()
            await query.message.reply_photo(
                photo=image_url,
                caption=safe_truncate(caption),
                reply_markup=back_kb,
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        except Exception:
            pass  # Fall back to text message if photo delivery fails

    # Fallback text message inspection if no artwork URL is present
    await query.message.edit_text(
        safe_truncate(caption),
        reply_markup=back_kb,
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_callback_query(filters.regex(r"^cz_method$"))
async def cb_cardz_methodology(client: Client, query: CallbackQuery):
    await query.answer()
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Browse Pokémon", callback_data="cz_list_pokemon_1"),
            InlineKeyboardButton("🏠 Home", callback_data="cz_home"),
        ]
    ])
    text = (
        "📐 **CardZ Marketcap Methodology & Standards**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "• **Market Cap Formula:** `PSA 10 Reference Price × Verified PSA 10 Population`.\n"
        "• **PSA 10 Strict Standard:** Only verified PSA 10 Gem Mint copies count toward population.\n"
        "• **Visual Artwork Integration:** Displays high-resolution card pictures directly inside Telegram when inspecting individual entries.\n"
        "• **Daily Snapshots:** Rebuilt daily with an explicit snapshot generation ID and effective date."
    )
    if query.message.photo:
        await query.message.delete()
        await query.message.reply_text(safe_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else:
        await query.message.edit_text(safe_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^cz_snapshot$"))
async def cb_cardz_snapshot(client: Client, query: CallbackQuery):
    await query.answer("Checking latest API snapshot...")
    res = await fetch_cardz_market(scope="pokemon", page=1)
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Open Rankings", callback_data="cz_list_pokemon_1"),
            InlineKeyboardButton("🏠 Home", callback_data="cz_home"),
        ]
    ])
    if not res["success"]:
        err_text = f"❌ **Could not reach API:** `{res['error']}`"
        if query.message.photo:
            await query.message.delete()
            return await query.message.reply_text(err_text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        return await query.message.edit_text(err_text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    text = (
        "📅 **Live API Snapshot Status**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Endpoint:** `cardzmarketcap.com/api/v1/market`\n"
        f"• **Effective Date:** `{res['snapshot_date']}`\n"
        f"• **Snapshot Generation:** `{res['generation']}`\n"
        f"• **Items Fetched (Page 1):** `{len(res['items'])}`\n"
        "• **Currency Basis:** `USD ($)`"
    )
    if query.message.photo:
        await query.message.delete()
        await query.message.reply_text(safe_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else:
        await query.message.edit_text(safe_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^cz_close$"))
async def cb_cardz_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
