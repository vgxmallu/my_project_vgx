import re
import httpx
from bs4 import BeautifulSoup
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app


def safe_truncate(text: str, max_length: int = 3800) -> str:
    """Safely truncates text to stay well within Telegram's 4000 character limit."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n\n... _(Output truncated due to length limitations)_"


def normalize_tag(raw_tag: str) -> str:
    """Cleans user input tag (removes #, spaces, converts O to 0)."""
    return raw_tag.replace("#", "").strip().upper().replace("O", "0")


async def fetch_public_player_details(tag: str) -> dict:
    """Fetches and parses real player stats from Brawlify without needing an API key."""
    clean_tag = normalize_tag(tag)
    url = f"https://brawlify.com/player/{clean_tag}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 404:
                return {"success": False, "error": f"Player `#{clean_tag}` not found."}
            if resp.status_code != 200:
                return {"success": False, "error": f"Tracker returned HTTP `{resp.status_code}`."}

            soup = BeautifulSoup(resp.text, "html.parser")
            page_text = soup.get_text(" | ", strip=True)

            # Extract Player Name from H1 or Title
            h1 = soup.find("h1")
            player_name = h1.get_text(strip=True) if h1 else None
            if not player_name or len(player_name) > 40:
                title_text = soup.title.string if soup.title else ""
                match_name = re.search(r"^(.*?)\s*\(#", title_text)
                player_name = match_name.group(1).strip() if match_name else f"Player #{clean_tag}"

            # Helper to extract stat values next to known labels on the profile page
            def extract_stat(label_pattern: str) -> str:
                pattern = re.compile(rf"{label_pattern}\s*\|\s*([0-9,]+)", re.IGNORECASE)
                m = pattern.search(page_text)
                if m:
                    return m.group(1)
                # Reverse order check (Value | Label)
                rev_pattern = re.compile(rf"([0-9,]+)\s*\|\s*{label_pattern}", re.IGNORECASE)
                m_rev = rev_pattern.search(page_text)
                return m_rev.group(1) if m_rev else "N/A"

            trophies = extract_stat(r"Trophies")
            highest_trophies = extract_stat(r"Highest Trophies")
            victories_3v3 = extract_stat(r"3v3 Victories|3 vs 3 Victories")
            solo_victories = extract_stat(r"Solo Victories|Solo Showdown")
            duo_victories = extract_stat(r"Duo Victories|Duo Showdown")
            exp_level = extract_stat(r"Level|Experience")

            # Extract Club Name if linked
            club_link = soup.find("a", href=re.compile(r"/club/"))
            club_name = club_link.get_text(strip=True) if club_link else "No Club"

            # Extract Brawlers list from brawler cards/links
            brawlers = []
            for img in soup.find_all("img", alt=True):
                alt_text = img["alt"].strip()
                if alt_text and len(alt_text) < 25 and alt_text not in brawlers:
                    # Filter common UI icons
                    if not any(w in alt_text.lower() for w in ["logo", "icon", "trophy", "brawlify", "banner", "pin"]):
                        brawlers.append(alt_text)

            return {
                "success": True,
                "tag": clean_tag,
                "name": player_name,
                "trophies": trophies,
                "highest_trophies": highest_trophies,
                "victories_3v3": victories_3v3,
                "solo_victories": solo_victories,
                "duo_victories": duo_victories,
                "exp_level": exp_level,
                "club": club_name,
                "brawlers": brawlers[:30],
                "url": url,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}


def build_player_keyboard(tag: str, view: str = "stats") -> InlineKeyboardMarkup:
    """Inline controls for switching between Stats, Brawlers, and Refresh."""
    buttons = []
    if view == "stats":
        buttons.append([
            InlineKeyboardButton("🤖 View Brawlers", callback_data=f"bsp_brawlers_{tag}"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"bsp_refresh_{tag}")
        ])
    else:
        buttons.append([
            InlineKeyboardButton("📊 Back to Stats", callback_data=f"bsp_stats_{tag}"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"bsp_refresh_{tag}")
        ])

    buttons.append([
        InlineKeyboardButton("🌐 Open Full Web Profile", url=f"https://brawlify.com/player/{tag}"),
        InlineKeyboardButton("❌ Close", callback_data="bsp_close")
    ])
    return InlineKeyboardMarkup(buttons)


def format_stats_message(data: dict) -> str:
    return (
        f"⭐ **{data['name']}** (`#{data['tag']}`)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• 🏆 **Trophies:** `{data['trophies']}`\n"
        f"• 📈 **Highest Trophies:** `{data['highest_trophies']}`\n"
        f"• 🛡️ **Club:** `{data['club']}`\n"
        f"• 🎖️ **Exp Level:** `{data['exp_level']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• 🎮 **3v3 Victories:** `{data['victories_3v3']}`\n"
        f"• 🥇 **Solo Victories:** `{data['solo_victories']}`\n"
        f"• 🥈 **Duo Victories:** `{data['duo_victories']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )


# ==========================================
# --- COMMAND HANDLER (ANY PLAYER TAG) ---
# ==========================================

@app.on_message(filters.command(["player", "bs", "stats", "brawl"]))
async def cmd_lookup_any_player(client: Client, message: Message):
    """Command: /player #TAG - Looks up any Brawl Stars player without an API key."""
    if len(message.command) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/player #TAG`\n"
            "_Example:_ `/player #9C98R9Q00`",
            parse_mode=ParseMode.MARKDOWN
        )

    raw_tag = message.command[1]
    clean_tag = normalize_tag(raw_tag)

    if len(clean_tag) < 3:
        return await message.reply_text("⚠️ Please enter a valid player tag (e.g. `#9C98R9Q00`).", parse_mode=ParseMode.MARKDOWN)

    msg = await message.reply_text(f"🔍 Looking up player details for `#{clean_tag}`...")
    data = await fetch_public_player_details(clean_tag)

    if not data["success"]:
        return await msg.edit_text(
            f"❌ **Lookup Failed:** {data['error']}",
            parse_mode=ParseMode.MARKDOWN
        )

    await msg.edit_text(
        safe_truncate(format_stats_message(data)),
        reply_markup=build_player_keyboard(clean_tag, view="stats"),
        parse_mode=ParseMode.MARKDOWN
    )


# ==========================================
# --- INLINE CALLBACK HANDLERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^bsp_(stats|refresh)_([A-Z0-9]+)$"))
async def cb_player_stats_or_refresh(client: Client, query: CallbackQuery):
    action, tag = query.matches[0].group(1), query.matches[0].group(2)
    await query.answer("Refreshing player stats..." if action == "refresh" else "Loading stats...")

    data = await fetch_public_player_details(tag)
    if not data["success"]:
        return await query.answer(f"Error: {data['error']}", show_alert=True)

    await query.message.edit_text(
        safe_truncate(format_stats_message(data)),
        reply_markup=build_player_keyboard(tag, view="stats"),
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^bsp_brawlers_([A-Z0-9]+)$"))
async def cb_player_brawlers(client: Client, query: CallbackQuery):
    tag = query.matches[0].group(1)
    await query.answer("Loading brawlers...")

    data = await fetch_public_player_details(tag)
    if not data["success"]:
        return await query.answer(f"Error: {data['error']}", show_alert=True)

    brawler_list = ", ".join(data["brawlers"]) if data["brawlers"] else "No brawler details visible on public cache."
    text = (
        f"🤖 **BRAWLERS — {data['name']}** (`#{tag}`)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{brawler_list}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await query.message.edit_text(
        safe_truncate(text),
        reply_markup=build_player_keyboard(tag, view="brawlers"),
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^bsp_close$"))
async def cb_player_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
