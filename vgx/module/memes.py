import random
import httpx
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app

# In-memory global cache for Imgflip memes list to ensure fast Next/Prev navigation
MEME_CACHE = []

# --- API FETCH HELPER ---
async def get_imgflip_memes():
    """Fetches popular meme templates from Imgflip public API."""
    global MEME_CACHE
    if MEME_CACHE:
        return MEME_CACHE

    url = "https://api.imgflip.com/get_memes"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            if data.get("success"):
                MEME_CACHE = data["data"]["memes"]
                return MEME_CACHE
            return []
        except Exception as e:
            print(f"Imgflip API Error: {e}")
            return []


# --- UI KEYBOARD BUILDERS ---
def get_meme_keyboard(index: int, total: int):
    """Interactive navigation controls exclusively using callback_data."""
    prev_idx = max(0, index - 1)
    next_idx = min(total - 1, index + 1)

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⬅️ Prev", callback_data=f"meme_nav_{prev_idx}"),
            InlineKeyboardButton(f"🎭 {index + 1} / {total}", callback_data="meme_noop"),
            InlineKeyboardButton("Next ➡️", callback_data=f"meme_nav_{next_idx}")
        ],
        [
            InlineKeyboardButton("🔀 Random Meme", callback_data="meme_random"),
            InlineKeyboardButton("📢 Send to Group", callback_data="meme_group_broadcast")
        ],
        [
            InlineKeyboardButton("❌", callback_data="close")
        ]
    ])


# --- COMMAND HANDLERS ---
@app.on_message(filters.command("memes"))
async def memes_command(client: Client, message: Message):
    """Command: /memes - Opens the interactive meme browser in private or group chat."""
    memes = await get_imgflip_memes()
    if not memes:
        return await message.reply_text("❌ Failed to fetch memes from Imgflip. Please try again later.")

    # Start at index 0 (First meme)
    meme = memes[0]
    name = meme.get("name", "Awesome Meme")
    url = meme.get("url")

    caption = (
        f"🎭 **Imgflip Meme Hub**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 **Title:** `{name}`\n"
        f"📌 *Use the buttons below to flip through pages!*"
    )

    kb = get_meme_keyboard(0, len(memes))
    await message.reply_photo(photo=url, caption=caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("gmeme"))
async def group_meme_command(client: Client, message: Message):
    """Command: /gmeme - Instantly pulls a trending random meme formatted for group chats."""
    memes = await get_imgflip_memes()
    if not memes:
        return await message.reply_text("❌ Failed to fetch memes.")

    meme = random.choice(memes)
    name = meme.get("name", "Group Meme")
    url = meme.get("url")

    caption = (
        f"🔥 **Trending Group Meme!**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 **{name}**\n"
        f"💬 *Shared via Bot Community Hub* ✨"
    )

    share_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Get Another Random Meme", callback_data="meme_random")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

    await message.reply_photo(photo=url, caption=caption, reply_markup=share_kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^meme_noop$"))
async def cb_meme_noop(client: Client, query: CallbackQuery):
    await query.answer("🎭 Imgflip Meme Gallery Index", show_alert=False)


@app.on_callback_query(filters.regex(r"^meme_nav_(?P<idx>\d+)$"))
async def cb_meme_navigation(client: Client, query: CallbackQuery):
    idx = int(query.matches[0].group("idx"))
    memes = await get_imgflip_memes()

    if not memes or idx >= len(memes):
        return await query.answer("⚠️ End of meme gallery reached.", show_alert=True)

    await query.answer(f"Loading meme {idx + 1} of {len(memes)}...")
    meme = memes[idx]
    name = meme.get("name", "Meme")
    url = meme.get("url")

    caption = (
        f"🎭 **Imgflip Meme Hub**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 **Title:** `{name}`\n"
        f"📌 *Use the buttons below to flip through pages!*"
    )

    kb = get_meme_keyboard(idx, len(memes))
    try:
        await query.message.edit_media(
            media=InputMediaPhoto(media=url, caption=caption, parse_mode=ParseMode.MARKDOWN),
            reply_markup=kb
        )
    except Exception:
        # Fallback if edit_media encounters issues with caption formatting
        try:
            await query.message.delete()
            await query.message.reply_photo(photo=url, caption=caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass


@app.on_callback_query(filters.regex(r"^meme_random$"))
async def cb_meme_random(client: Client, query: CallbackQuery):
    memes = await get_imgflip_memes()
    if not memes:
        return await query.answer("❌ Error loading memes.", show_alert=True)

    idx = random.randint(0, len(memes) - 1)
    meme = memes[idx]
    name = meme.get("name", "Random Meme")
    url = meme.get("url")

    await query.answer("🎲 Rolling a random meme...")
    caption = (
        f"🎭 **Imgflip Meme Hub**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 **Title:** `{name}`\n"
        f"📌 *Randomized from gallery!*"
    )

    kb = get_meme_keyboard(idx, len(memes))
    try:
        await query.message.delete()
        await query.message.reply_photo(photo=url, caption=caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass


@app.on_callback_query(filters.regex(r"^meme_group_broadcast$"))
async def cb_meme_group_broadcast(client: Client, query: CallbackQuery):
    """Allows users to trigger an inline query share to easily post memes into group chats."""
    user = query.from_user
    await query.answer("Preparing meme for group broadcasting...", show_alert=True)

    broadcast_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Broadcast to Group Chat", switch_inline_query="Check out this hilarious meme!")]
    ])

    await query.message.reply_text(
        f"📢 **Group Meme Broadcasting**\n\n"
        f"Click below to quickly share this current meme session with your active community groups! ✨",
        reply_markup=broadcast_kb
    )
