import os
import httpx
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config

# API Key Management (Supports config.py or Environment Variables)
BASE_URL = "https://newsapi.org/v2"

# In-memory session cache to hold current article datasets for pagination & in-bot reading
NEWS_CACHE = {}

# --- API FETCH HELPER ---
async def fetch_world_news(category: str = "general"):
    """Fetches top world headlines from NewsAPI.org asynchronously using httpx."""
    url = f"{BASE_URL}/top-headlines"
    params = {
        "apiKey": Comfig.NEWS_API_KEY,
        "language": "en",
        "category": category,
        "pageSize": 10
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=10.0)
            if response.status_code == 401:
                return {"error": "⚠️ Invalid NewsAPI Key. Please verify your API token."}
            elif response.status_code == 429:
                return {"error": "⚠️ Rate limit exceeded. Please try again later."}
            response.raise_for_status()
            data = response.json()
            return data.get("articles", [])
        except Exception as e:
            return {"error": f"⚠️ Connection Error: {str(e)}"}


# --- UI KEYBOARD BUILDERS ---
def get_news_main_menu():
    """Main interactive hub for World News."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌍 Top World News", callback_data="news_cat_general"),
            InlineKeyboardButton("💼 Business & Tech", callback_data="news_cat_business")
        ],
        [
            InlineKeyboardButton("⚽ Sports & Fun", callback_data="news_cat_sports"),
            InlineKeyboardButton("🔬 Science & Health", callback_data="news_cat_science")
        ],
        [
            InlineKeyboardButton("🎬 Entertainment", callback_data="news_cat_entertainment"),
            InlineKeyboardButton("❌ Close", callback_data="news_close")
        ]
    ])

def get_article_keyboard(category: str, index: int, total: int):
    """Strict callback-controlled navigation and reading menu."""
    prev_idx = max(0, index - 1)
    next_idx = min(total - 1, index + 1)

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⬅️ Prev", callback_data=f"news_nav_{category}_{prev_idx}"),
            InlineKeyboardButton(f"📖 {index + 1} / {total}", callback_data="news_noop"),
            InlineKeyboardButton("Next ➡️", callback_data=f"news_nav_{category}_{next_idx}")
        ],
        [
            InlineKeyboardButton("📄 Read Full Text (In-Bot)", callback_data=f"news_read_{category}_{index}")
        ],
        [
            InlineKeyboardButton("👥 Read with Group Members", callback_data=f"news_group_{category}_{index}")
        ],
        [
            InlineKeyboardButton("🏠 Main Menu", callback_data="news_home"),
            InlineKeyboardButton("❌ Close", callback_data="news_close")
        ]
    ])


# --- COMMAND HANDLERS ---
@app.on_message(filters.command("newsz"))
async def news_command(client: Client, message: Message):
    """Command: /newsz - Opens the World News Control Center."""
    welcome_text = (
        "📰 **Global World News Control Center**\n\n"
        "Welcome! Explore breaking global headlines, live stories, and read articles with your community powered by **NewsAPI**.\n\n"
        "👇 **Select a category below to browse stories:**"
    )
    await message.reply_text(welcome_text, reply_markup=get_news_main_menu(), parse_mode=ParseMode.MARKDOWN)


# --- STRICT REGEX CALLBACK ROUTERS ---

@app.on_callback_query(filters.regex(r"^news_home$"))
async def cb_news_home(client: Client, query: CallbackQuery):
    await query.answer()
    welcome_text = (
        "📰 **Global World News Control Center**\n\n"
        "Welcome! Explore breaking global headlines, live stories, and read articles with your community powered by **NewsAPI**.\n\n"
        "👇 **Select a category below to browse stories:**"
    )
    await query.message.edit_text(welcome_text, reply_markup=get_news_main_menu(), parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^news_close$"))
async def cb_news_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()

@app.on_callback_query(filters.regex(r"^news_noop$"))
async def cb_news_noop(client: Client, query: CallbackQuery):
    await query.answer("📌 Current Article Position", show_alert=False)

@app.on_callback_query(filters.regex(r"^news_cat_(?P<cat>[a-z]+)$"))
async def cb_news_category(client: Client, query: CallbackQuery):
    category = query.matches[0].group("cat")
    await query.answer(f"Fetching world {category} news...")

    articles = await fetch_world_news(category)
    if isinstance(articles, dict) and "error" in articles:
        return await query.message.edit_text(articles["error"], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back", callback_data="news_home")]]))

    if not articles:
        return await query.message.edit_text(f"❌ No articles found for category `{category}`.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back", callback_data="news_home")]]))

    # Cache articles for session navigation
    user_id = query.from_user.id
    NEWS_CACHE[user_id] = {"articles": articles, "category": category}

    article = articles[0]
    title = article.get("title", "No Title")
    desc = article.get("description", "No summary available.")
    source = article.get("source", {}).get("name", "Global Source")
    published = article.get("publishedAt", "")[:10]

    text = (
        f"🌐 **World News | Category: `{category.upper()}`**\n"
        f"📌 **Source:** `{source}` | 📅 `{published}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"**{title}**\n\n"
        f"{desc if desc else ''}"
    )

    kb = get_article_keyboard(category, 0, len(articles))
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^news_nav_(?P<cat>[a-z]+)_(?P<idx>\d+)$"))
async def cb_news_navigation(client: Client, query: CallbackQuery):
    category = query.matches[0].group("cat")
    idx = int(query.matches[0].group("idx"))
    user_id = query.from_user.id

    session = NEWS_CACHE.get(user_id)
    articles = session.get("articles") if session else None

    if not articles:
        articles = await fetch_world_news(category)
        NEWS_CACHE[user_id] = {"articles": articles, "category": category}

    if idx >= len(articles):
        return await query.answer("⚠️ End of list reached.", show_alert=True)

    await query.answer("Loading article...")
    article = articles[idx]
    title = article.get("title", "No Title")
    desc = article.get("description", "No summary available.")
    source = article.get("source", {}).get("name", "Global Source")
    published = article.get("publishedAt", "")[:10]

    text = (
        f"🌐 **World News | Category: `{category.upper()}`**\n"
        f"📌 **Source:** `{source}` | 📅 `{published}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"**{title}**\n\n"
        f"{desc if desc else ''}"
    )

    kb = get_article_keyboard(category, idx, len(articles))
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^news_read_(?P<cat>[a-z]+)_(?P<idx>\d+)$"))
async def cb_news_read_full(client: Client, query: CallbackQuery):
    """In-bot full text article reader (No external link required)."""
    category = query.matches[0].group("cat")
    idx = int(query.matches[0].group("idx"))
    user_id = query.from_user.id

    session = NEWS_CACHE.get(user_id)
    articles = session.get("articles") if session else []

    if not articles or idx >= len(articles):
        return await query.answer("⚠️ Article data expired. Please refresh category.", show_alert=True)

    await query.answer("Opening full article text...")
    article = articles[idx]
    title = article.get("title", "No Title")
    content = article.get("content") or article.get("description") or "Full text content not available from this publisher source."
    source = article.get("source", {}).get("name", "Global Source")
    author = article.get("author", "Unknown Author")

    # Clean up NewsAPI truncation artifact '[+1234 chars]' if present
    if "[+" in content:
        content = content.split("[+")[0]

    text = (
        f"📖 **In-Bot Article Reader**\n"
        f"📌 **Source:** `{source}` | ✍️ **Author:** `{author}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"**{title}**\n\n"
        f"{content}\n\n"
        f"*(Fetched securely via NewsAPI)*"
    )

    back_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Headlines", callback_data=f"news_cat_{category}")]
    ])
    await query.message.edit_text(text, reply_markup=back_kb, parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^news_group_(?P<cat>[a-z]+)_(?P<idx>\d+)$"))
async def cb_read_with_group(client: Client, query: CallbackQuery):
    """Exclusive Feature: Read news with group members by formatting a collaborative discussion card."""
    category = query.matches[0].group("cat")
    idx = int(query.matches[0].group("idx"))
    user_id = query.from_user.id
    user = query.from_user

    session = NEWS_CACHE.get(user_id)
    articles = session.get("articles") if session else []

    if not articles or idx >= len(articles):
        return await query.answer("⚠️ Article expired. Please reload.", show_alert=True)

    await query.answer("Generating group session card...", show_alert=True)
    article = articles[idx]
    title = article.get("title", "Breaking News")
    source = article.get("source", {}).get("name", "Global Source")

    group_session_card = (
        f"👥 **Community Group Reading Session**\n"
        f"📢 *Started by @{user.username or user.first_name}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📰 **{title}**\n"
        f"📌 **Source:** `{source}`\n\n"
        f"💬 *Group members: Discuss your thoughts on this story below!* 👇"
    )

    # Use inline sharing trigger to allow sending this into any active group chat
    share_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share Session to Group", switch_inline_query=f"Breaking News Discussion: {title[:40]}...")]
    ])

    await query.message.reply_text(group_session_card, reply_markup=share_kb, parse_mode=ParseMode.MARKDOWN)
