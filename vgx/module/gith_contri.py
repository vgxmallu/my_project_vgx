import io
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from pyrogram.enums import ParseMode
from vgx import app

# --- CONFIGURATION ---
CONTRIB_BASE_URL = "https://github-contributions.vercel.app"

# Mapping display names to API theme slugs (optimized for Telegram 64-byte callback limits)
THEMES = {
    "GitHub": "github",
    "Classic": "classic",
    "Dark": "dark",
    "Halloween": "halloween",
    "Teal": "teal",
    "@left_pad": "left-pad",
    "Dracula": "dracula",
    "Blue": "blue",
    "Panda 🐼": "panda",
    "Sunny": "sunny",
    "Pink": "pink",
    "YlGnBu": "ylgnbu",
    "Solarized Dark": "soldark",
    "Solarized Light": "sollight"
}

# Reverse map for API request URL lookup
SLUG_TO_API = {
    "github": "github",
    "classic": "classic",
    "dark": "dark",
    "halloween": "halloween",
    "teal": "teal",
    "left-pad": "left-pad",
    "dracula": "dracula",
    "blue": "blue",
    "panda": "panda",
    "sunny": "sunny",
    "pink": "pink",
    "ylgnbu": "ylgnbu",
    "soldark": "solarized-dark",
    "sollight": "solarized-light"
}


def safe_truncate(text: str, max_length: int = 3800) -> str:
    """Safely truncates text to stay well within Telegram's 4000 character limit."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n\n... _(Output truncated due to length limitations)_"


def get_contrib_menu(username: str = "octocat", current_theme_slug: str = "github") -> InlineKeyboardMarkup:
    """Generates an organized multi-row interactive keyboard dashboard for all 14 themes."""
    theme_items = list(THEMES.items())
    keyboard = []
    
    # Build a 2-column grid for themes
    for i in range(0, len(theme_items), 2):
        row = []
        for name, slug in theme_items[i:i+2]:
            prefix = "🟢 " if slug == current_theme_slug else "🎨 "
            row.append(InlineKeyboardButton(f"{prefix}{name}", callback_data=f"gh_th_{username}_{slug}"))
        keyboard.append(row)

    # Action control buttons
    keyboard.append([
        InlineKeyboardButton("🔄 Refresh", callback_data=f"gh_ref_{username}_{current_theme_slug}"),
        InlineKeyboardButton("🌐 Web App", url=CONTRIB_BASE_URL)
    ])
    keyboard.append([InlineKeyboardButton("❌ Close", callback_data="gh_close")])

    return InlineKeyboardMarkup(keyboard)


@app.on_message(filters.command(["contributions", "githubcontrib", "gitgraph"]))
async def cmd_github_contributions(client: Client, message: Message):
    """Command: /contributions <username> - Generates a GitHub contribution chart with theme selectors."""
    args = message.command
    username = args[1].strip() if len(args) > 1 else "octocat"
    
    msg = await message.reply_text(f"📊 Generating contribution chart for `@{username}`...")

    default_slug = "github"
    api_theme = SLUG_TO_API[default_slug]
    chart_url = f"{CONTRIB_BASE_URL}/api/v1/{username}?theme={api_theme}"

    caption = (
        f"🐙 **GITHUB CONTRIBUTIONS CHART**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Target User:** `@{username}`\n"
        f"• **Active Theme:** `GitHub`\n"
        f"• **Source:** `{CONTRIB_BASE_URL}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    try:
        await message.reply_photo(
            photo=chart_url,
            caption=safe_truncate(caption),
            reply_markup=get_contrib_menu(username, default_slug),
            parse_mode=ParseMode.MARKDOWN
        )
        await msg.delete()
    except Exception:
        fallback_text = (
            f"{caption}\n\n"
            f"🔗 **Direct Link:** [View Contributions Chart]({chart_url})"
        )
        await msg.edit_text(
            safe_truncate(fallback_text),
            reply_markup=get_contrib_menu(username, default_slug),
            parse_mode=ParseMode.MARKDOWN
        )


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^gh_th_(?P<user>[^_]+)_(?P<slug>.+)$"))
async def cb_github_theme_switch(client: Client, query: CallbackQuery):
    match = query.matches[0]
    username = match.group("user")
    slug = match.group("slug")
    
    api_theme = SLUG_TO_API.get(slug, "github")
    await query.answer(f"Applied theme successfully!")

    chart_url = f"{CONTRIB_BASE_URL}/api/v1/{username}?theme={api_theme}"
    
    # Find display name for caption
    display_name = next((k.replace("🟢 ", "").replace("🎨 ", "") for k, v in THEMES.items() if v == slug), slug.capitalize())

    caption = (
        f"🐙 **GITHUB CONTRIBUTIONS CHART**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Target User:** `@{username}`\n"
        f"• **Active Theme:** `{display_name}`\n"
        f"• **Source:** `{CONTRIB_BASE_URL}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    try:
        await query.message.edit_media(
            media=InputMediaPhoto(media=chart_url, caption=safe_truncate(caption), parse_mode=ParseMode.MARKDOWN),
            reply_markup=get_contrib_menu(username, slug)
        )
    except Exception:
        await query.message.edit_text(
            safe_truncate(f"{caption}\n\n🔗 **Chart URL:** {chart_url}"),
            reply_markup=get_contrib_menu(username, slug),
            parse_mode=ParseMode.MARKDOWN
        )


@app.on_callback_query(filters.regex(r"^gh_ref_(?P<user>[^_]+)_(?P<slug>.+)$"))
async def cb_github_refresh(client: Client, query: CallbackQuery):
    match = query.matches[0]
    username = match.group("user")
    slug = match.group("slug")
    
    await query.answer("Refreshed chart data ⚡")
    display_name = next((k for k, v in THEMES.items() if v == slug), "GitHub")

    caption = (
        f"🐙 **GITHUB CONTRIBUTIONS CHART** [Refreshed]\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Target User:** `@{username}`\n"
        f"• **Active Theme:** `{display_name}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    try:
        await query.message.edit_caption(
            caption=safe_truncate(caption),
            reply_markup=get_contrib_menu(username, slug)
        )
    except Exception:
        pass


@app.on_callback_query(filters.regex(r"^gh_close$"))
async def cb_github_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
