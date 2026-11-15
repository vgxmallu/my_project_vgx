import os
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app

# --- CONFIGURATION ---
TADDY_API_URL = "https://api.taddy.org"
TADDY_USER_ID = os.getenv("TADDY_USER_ID", "5749")
TADDY_API_KEY = os.getenv("TADDY_API_KEY", "19c8afb17499d8c3007057e43ab0ef1e44d0daa219c8ab8a3794f71c7f06a812a19d871c64a127b50ba177085604145200")


async def taddy_graphql_query(query: str) -> dict:
    """Helper utility for executing asynchronous GraphQL queries against Taddy API."""
    headers = {
        "Content-Type": "application/json",
        "X-USER-ID": str(TADDY_USER_ID),
        "X-API-KEY": str(TADDY_API_KEY)
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(TADDY_API_URL, json={"query": query}, headers=headers)
            if response.status_code == 200:
                result = response.json()
                if "errors" in result:
                    return {"success": False, "error": result["errors"][0].get("message", "GraphQL Error")}
                return {"success": True, "data": result.get("data", {})}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_taddy_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for Taddy Podcast controls."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Search Podcasts", callback_data="taddy_search_prompt"),
            InlineKeyboardButton("📈 US Top Charts", callback_data="taddy_charts")
        ],
        [
            InlineKeyboardButton("📻 Sample Series lookup", callback_data="taddy_sample_series"),
            InlineKeyboardButton("📚 Taddy Docs", url="https://taddy.org/developers/podcast-api")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="taddy_close")]
    ])


@app.on_message(filters.command(["taddy", "podcast", "podcasts"]))
async def cmd_taddy_dashboard(client: Client, message: Message):
    """Command: /taddy - Opens the master interactive Taddy Podcast API dashboard."""
    text = (
        "🎙️ **Taddy Podcast Intelligence Suite**\n\n"
        "Explore over 4 million podcasts, 200 million episodes, full-text search, automatic transcripts, "
        "chapters, and top charts using the GraphQL engine.\n\n"
        "Select an action below:"
    )
    await message.reply_text(text, reply_markup=get_taddy_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.command(["podcastsearch", "psearch"]))
async def cmd_taddy_search(client: Client, message: Message):
    """Command: /podcastsearch <term> - Full-text search across podcasts and episodes."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/podcastsearch <search term>`\n\n_Example:_ `/podcastsearch true crime`",
            parse_mode=ParseMode.MARKDOWN
        )

    term = message.text.partition(" ")[2].strip()
    msg = await message.reply_text(f"🔍 Searching Taddy registry for `{term}`...")

    query = f"""
    {{
      search(term: "{term}", limitPerPage: 5) {{
        podcastSeries {{
          uuid
          name
          totalEpisodesCount
          genres
          contentType
        }}
      }}
    }}
    """

    res = await taddy_graphql_query(query)
    if not res["success"]:
        return await msg.edit_text(f"❌ Taddy API Error:\n`{res['error']}`", parse_mode=ParseMode.MARKDOWN)

    series_list = res["data"].get("search", {}).get("podcastSeries", [])
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="taddy_home")]])

    if not series_list:
        return await msg.edit_text(f"📭 No podcast series found for query: `{term}`", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    output = [f"🔍 **Search Results for:** `{term}`\n━━━━━━━━━━━━━━━━━━━━━━"]
    for s in series_list:
        output.append(
            f"• **{s.get('name')}**\n"
            f"  - Episodes: `{s.get('totalEpisodesCount', 'N/A')}`\n"
            f"  - Type: `{s.get('contentType', 'AUDIO')}`\n"
            f"  - UUID: `{s.get('uuid')}`\n"
        )

    await msg.edit_text("\n".join(output), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^taddy_home$"))
async def cb_taddy_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🎙️ **Taddy Podcast Intelligence Suite**\n\n"
        "Explore over 4 million podcasts, 200 million episodes, full-text search, automatic transcripts, "
        "chapters, and top charts using the GraphQL engine.\n\n"
        "Select an action below:"
    )
    await query.message.edit_text(text, reply_markup=get_taddy_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^taddy_sample_series$"))
async def cb_taddy_sample(client: Client, query: CallbackQuery):
    await query.answer("Fetching sample podcast series...")
    
    query_str = """
    {
      getPodcastSeries(name: "This American Life") {
        uuid
        name
        description
        totalEpisodesCount
        language
        contentType
        popularityRank
      }
    }
    """
    res = await taddy_graphql_query(query_str)
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="taddy_home")]])

    if not res["success"]:
        return await query.message.edit_text(f"❌ Error: `{res['error']}`", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    podcast = res["data"].get("getPodcastSeries")
    if not podcast:
        return await query.message.edit_text("Podcast not found.", reply_markup=keyboard)

    response_text = (
        f"📻 **PODCAST SERIES DETAILS**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Name:** `{podcast.get('name')}`\n"
        f"• **Total Episodes:** `{podcast.get('totalEpisodesCount')}`\n"
        f"• **Language:** `{podcast.get('language')}` | **Type:** `{podcast.get('contentType')}`\n"
        f"• **Popularity Rank:** `{podcast.get('popularityRank')}`\n"
        f"• **UUID:** `{podcast.get('uuid')}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await query.message.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^taddy_charts$"))
async def cb_taddy_charts(client: Client, query: CallbackQuery):
    await query.answer("Fetching US Top Charts...")

    query_str = """
    {
      getTopChartsByCountry(taddyType: PODCASTSERIES, country: UNITED_STATES_OF_AMERICA, page: 1, limitPerPage: 5) {
        podcastSeries {
          name
          totalEpisodesCount
        }
      }
    }
    """
    res = await taddy_graphql_query(query_str)
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="taddy_home")]])

    if not res["success"]:
        return await query.message.edit_text(f"❌ Error: `{res['error']}`", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    charts = res["data"].get("getTopChartsByCountry", {}).get("podcastSeries", [])
    if not charts:
        return await query.message.edit_text("No top charts data available.", reply_markup=keyboard)

    list_items = "\n".join([f"{i+1}. **{p.get('name')}** (`{p.get('totalEpisodesCount', 0)} eps`)" for i, p in enumerate(charts)])
    
    response_text = (
        f"📈 **US TOP PODCAST CHARTS**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{list_items}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await query.message.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^taddy_search_prompt$"))
async def cb_taddy_search_prompt(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="taddy_home")]])
    await query.message.edit_text(
        "🔍 **How to Search Taddy Podcasts:**\n\n"
        "Send the command directly in chat followed by your keyword search term:\n"
        "`/podcastsearch technology` or `/psearch business`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^taddy_close$"))
async def cb_taddy_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()

