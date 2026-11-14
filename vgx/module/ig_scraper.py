import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config  # Must contain RAPIDAPI_KEY

# --- CONFIGURATION & HEADERS ---
RAPIDAPI_HOST = "instagram-scraper-stable-api.p.rapidapi.com"
BASE_URL = f"https://{RAPIDAPI_HOST}"


def get_rapid_api_key() -> str:
    """Retrieves RapidAPI key from config safely."""
    return getattr(Config, "IG_RAPIDAPI_KEY", None)


async def ig_api_request(endpoint: str, params: dict = None, method: str = "GET", json_data: dict = None) -> dict:
    """Centralized async request helper for Instagram Scraper Stable API."""
    key = get_rapid_api_key()
    if not key:
        return {"error": "Missing RapidAPI key in config.py"}

    headers = {
        "x-rapidapi-key": key,
        "x-rapidapi-host": RAPIDAPI_HOST,
        "Content-Type": "application/json"
    }

    url = f"{BASE_URL}/{endpoint.lstrip('/')}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if method.upper() == "POST":
                resp = await client.post(url, headers=headers, json=json_data, params=params)
            else:
                resp = await client.get(url, headers=headers, params=params)

            if resp.status_code == 200:
                return resp.json()
            print(f"Instagram API Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"Instagram API Exception: {e}")
        return {}


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_ig_main_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for Instagram tools."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 User Profile", callback_data="ig_menu_profile"),
            InlineKeyboardButton("📸 User Posts", callback_data="ig_menu_posts")
        ],
        [
            InlineKeyboardButton("🎥 User Reels", callback_data="ig_menu_reels"),
            InlineKeyboardButton("⏳ User Stories", callback_data="ig_menu_stories")
        ],
        [
            InlineKeyboardButton("🔍 Search Instagram", callback_data="ig_menu_search"),
            InlineKeyboardButton("🔗 Post Details / Info", callback_data="ig_menu_postinfo")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="ig_close")]
    ])


@app.on_message(filters.command(["ig", "instagram", "igsuite"]))
async def cmd_ig_dashboard(client: Client, message: Message):
    """Command: /ig - Opens the interactive Instagram Scraper suite dashboard."""
    text = (
        "📸 **Instagram Scraper Stable Intelligence Suite**\n\n"
        "Extract real-time public data, profiles, posts, reels, stories, and search analytics "
        "using the interactive dashboard controls below:"
    )
    await message.reply_text(text, reply_markup=get_ig_main_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- 1. USER PROFILE / ACCOUNT DATA ---
# ==========================================

@app.on_message(filters.command(["igprofile", "iguser"]))
async def cmd_ig_profile(client: Client, message: Message):
    """Command: /igprofile <username> - Fetches public profile account data."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/igprofile <username>`\n\n"
            "_Example:_ `/igprofile instagram`",
            parse_mode=ParseMode.MARKDOWN
        )

    username = args[1].strip().lstrip("@")
    msg = await message.reply_text(f"🔍 Fetching profile data for `@{username}`...")

    # Typical RapidAPI endpoint structure for user info
    data = await ig_api_request("v1/info", params={"username_or_url": username})
    if not data or "error" in data:
        # Fallback query attempt
        data = await ig_api_request("user", params={"username": username})

    if not data:
        return await msg.edit_text(f"❌ Failed to retrieve profile for `@{username}`.")

    # Parse response fields safely
    user_info = data.get("data", data)
    full_name = user_info.get("full_name", "N/A")
    bio = user_info.get("biography", "No bio available.")
    followers = user_info.get("follower_count", user_info.get("followers", 0))
    following = user_info.get("following_count", user_info.get("following", 0))
    posts_count = user_info.get("media_count", user_info.get("posts_count", 0))
    is_verified = "✅ Yes" if user_info.get("is_verified") else "❌ No"
    is_private = "🔒 Yes" if user_info.get("is_private") else "🌐 Public"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Main Menu", callback_data="ig_home")]
    ])

    await msg.edit_text(
        f"👤 **Instagram Profile: @{username}**\n\n"
        f"• **Full Name:** `{full_name}`\n"
        f"• **Verified:** {is_verified} | **Account:** {is_private}\n"
        f"• **Followers:** `{followers:,}` | **Following:** `{following:,}`\n"
        f"• **Total Posts:** `{posts_count:,}`\n\n"
        f"• **Bio:**\n> {bio}",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


# ==========================================
# --- 2. USER POSTS & MEDIA ---
# ==========================================

@app.on_message(filters.command(["igposts", "igmedia"]))
async def cmd_ig_posts(client: Client, message: Message):
    """Command: /igposts <username> - Fetches recent posts and feed items."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/igposts <username>`",
            parse_mode=ParseMode.MARKDOWN
        )

    username = args[1].strip().lstrip("@")
    msg = await message.reply_text(f"📸 Fetching recent posts for `@{username}`...")

    data = await ig_api_request("v1/posts", params={"username_or_url": username})
    if not data:
        data = await ig_api_request("user/posts", params={"username": username})

    items = data.get("data", data.get("items", []))
    if not items or not isinstance(items, list):
        return await msg.edit_text(f"❌ No posts found or profile is private for `@{username}`.")

    summary_lines = [f"📸 **Recent Posts for @{username}** (Showing top {min(len(items), 5)})\n"]
    for idx, post in enumerate(items[:5], start=1):
        caption = post.get("caption", {}).get("text", post.get("caption", "No caption"))
        short_cap = caption[:45] + ("..." if len(caption) > 45 else "")
        likes = post.get("like_count", post.get("likes", 0))
        comments = post.get("comment_count", post.get("comments", 0))
        code = post.get("shortcode", "")
        url = f"https://instagram.com/p/{code}" if code else "#"

        summary_lines.append(f"**{idx}.** {short_cap}\n   ❤️ `{likes:,}` likes | 💬 `{comments:,}` comments\n   🔗 [View Post]({url})\n")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="ig_home")]])
    await msg.edit_text("\n".join(summary_lines), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


# ==========================================
# --- 3. USER REELS ---
# ==========================================

@app.on_message(filters.command(["igreels"]))
async def cmd_ig_reels(client: Client, message: Message):
    """Command: /igreels <username> - Fetches user reels."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/igreels <username>`", parse_mode=ParseMode.MARKDOWN)

    username = args[1].strip().lstrip("@")
    msg = await message.reply_text(f"🎥 Fetching reels for `@{username}`...")

    data = await ig_api_request("v1/reels", params={"username_or_url": username})
    items = data.get("data", data.get("items", []))

    if not items or not isinstance(items, list):
        return await msg.edit_text(f"❌ No reels found for `@{username}`.")

    summary = [f"🎥 **Reels for @{username}** (Top {min(len(items), 5)})\n"]
    for idx, reel in enumerate(items[:5], start=1):
        plays = reel.get("play_count", reel.get("video_view_count", 0))
        code = reel.get("shortcode", "")
        url = f"https://instagram.com/reel/{code}" if code else "#"
        summary.append(f"**{idx}.** Plays: `{plays:,}` | 🔗 [Watch Reel]({url})")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="ig_home")]])
    await msg.edit_text("\n".join(summary), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


# ==========================================
# --- 4. USER STORIES ---
# ==========================================

@app.on_message(filters.command(["igstories"]))
async def cmd_ig_stories(client: Client, message: Message):
    """Command: /igstories <username> - Fetches active stories."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/igstories <username>`", parse_mode=ParseMode.MARKDOWN)

    username = args[1].strip().lstrip("@")
    msg = await message.reply_text(f"⏳ Checking active stories for `@{username}`...")

    data = await ig_api_request("v1/stories", params={"username_or_url": username})
    stories = data.get("data", data.get("items", []))

    if not stories:
        return await msg.edit_text(f"📭 No active stories found for `@{username}` (or stories have expired).")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="ig_home")]])
    await msg.edit_text(
        f"⏳ **Active Stories Found:** `@{username}` has **{len(stories)}** active story item(s).",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


# ==========================================
# --- 5. SEARCH INSTAGRAM ---
# ==========================================

@app.on_message(filters.command(["igsearch"]))
async def cmd_ig_search(client: Client, message: Message):
    """Command: /igsearch <query> - Searches accounts or hashtags."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/igsearch <query>`", parse_mode=ParseMode.MARKDOWN)

    query = message.text.partition(" ")[2].strip()
    msg = await message.reply_text(f"🔍 Searching Instagram for `{query}`...")

    data = await ig_api_request("v1/search", params={"query": query})
    users = data.get("data", data.get("users", []))

    if not users:
        return await msg.edit_text(f"❌ No search results found for `{query}`.")

    lines = [f"🔍 **Search Results for:** `{query}`\n"]
    for u in users[:5]:
        user_obj = u.get("user", u)
        uname = user_obj.get("username", "")
        name = user_obj.get("full_name", "")
        verified = "✅" if user_obj.get("is_verified") else ""
        lines.append(f"• **@{uname}** {verified} — `{name}`")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="ig_home")]])
    await msg.edit_text("\n".join(lines), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^ig_home$"))
async def cb_ig_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "📸 **Instagram Scraper Stable Intelligence Suite**\n\n"
        "Select a tool or view your live API options below:"
    )
    await query.message.edit_text(text, reply_markup=get_ig_main_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^ig_menu_profile$"))
async def cb_ig_menu_profile(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="ig_home")]])
    await query.message.edit_text(
        "👤 **User Profile Extraction**\n\n"
        "Send the command in chat followed by any public username:\n\n"
        "`/igprofile instagram`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^ig_menu_posts$"))
async def cb_ig_menu_posts(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="ig_home")]])
    await query.message.edit_text(
        "📸 **User Posts Scraper**\n\n"
        "Fetch recent feed posts, captions, and engagement metrics:\n\n"
        "`/igposts instagram`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^ig_menu_reels$"))
async def cb_ig_menu_reels(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="ig_home")]])
    await query.message.edit_text(
        "🎥 **User Reels Scraper**\n\n"
        "Fetch user video reels and play counts:\n\n"
        "`/igreels instagram`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^ig_menu_stories$"))
async def cb_ig_menu_stories(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="ig_home")]])
    await query.message.edit_text(
        "⏳ **User Stories Scraper**\n\n"
        "Check active user stories:\n\n"
        "`/igstories instagram`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^ig_menu_search$"))
async def cb_ig_menu_search(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="ig_home")]])
    await query.message.edit_text(
        "🔍 **Instagram Search**\n\n"
        "Search profiles and accounts on the fly:\n\n"
        "`/igsearch technology`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^ig_menu_postinfo$"))
async def cb_ig_menu_postinfo(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="ig_home")]])
    await query.message.edit_text(
        "🔗 **Post Details & Comments**\n\n"
        "Pull comprehensive engagement details, comments, and likers for specific media URLs or shortcodes.",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^ig_close$"))
async def cb_ig_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
