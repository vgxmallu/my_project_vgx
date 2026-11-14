import asyncio
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config  # Must contain DETECT_LANGUAGE_API_KEY

# --- CONFIGURATION & ENDPOINTS ---
DETECT_URL = "https://ws.detectlanguage.com/v2/detect"

# In-memory infraction tracker: {user_id: warning_count}
USER_WARNINGS = {}
MAX_WARNINGS_BEFORE_BAN = 3


def get_detect_token() -> str:
    """Retrieves the Detect Language API key from config safely."""
    return getattr(Config, "DETECT_LANGUAGE_API_KEY", None)


async def detect_text_language(text: str) -> str:
    """Sends text to Detect Language API and returns the ISO language code."""
    token = get_detect_token()
    if not token or not text.strip():
        return "en"

    headers = {"Authorization": f"Bearer {token}"}
    payload = {"q": text.strip()}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(DETECT_URL, json=payload, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                detections = data.get("data", {}).get("detections", [])
                if detections:
                    return detections[0].get("language", "en")
        except Exception as e:
            print(f"Language Detection Exception: {e}")
        return "en"


async def is_user_admin(client: Client, chat_id: int, user_id: int) -> bool:
    """Helper to check if a user is an administrator or creator of the chat."""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False


# ==========================================
# --- GROUP MESSAGE ENFORCER ---
# ==========================================

@app.on_message(filters.group & ~filters.service & ~filters.bot)
async def enforce_english_only(client: Client, message: Message):
    """Monitors group messages, blocks non-English text, and attaches inline control buttons."""
    if not message.text and not message.caption:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    # Skip checks for administrators or creators
    if await is_user_admin(client, chat_id, user_id):
        return

    text_to_check = message.text or message.caption
    if len(text_to_check.strip()) < 3:
        return

    # Detect language
    lang_code = await detect_text_language(text_to_check)

    if lang_code and lang_code.lower() != "en":
        try:
            await message.delete()
        except Exception:
            return

        user_name = message.from_user.first_name
        USER_WARNINGS[user_id] = USER_WARNINGS.get(user_id, 0) + 1
        current_warnings = USER_WARNINGS[user_id]

        if current_warnings >= MAX_WARNINGS_BEFORE_BAN:
            try:
                await client.ban_chat_member(chat_id, user_id)
                
                # Ban message with inline Unban button
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔓 Unban User", callback_data=f"eng_unban_{user_id}")]
                ])
                
                await client.send_message(
                    chat_id,
                    f"🚫 **User Banned:** [{user_name}](tg://user?id={user_id}) was banned for repeated non-English messages.",
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            except Exception as e:
                print(f"Ban error: {e}")

        # Warning message with inline admin control buttons
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚠️ Unwarn", callback_data=f"eng_unwarn_{user_id}"),
                InlineKeyboardButton("🗑️ Dismiss", callback_data="eng_dismiss")
            ]
        ])

        await client.send_message(
            chat_id,
            f"⚠️ [{user_name}](tg://user?id={user_id}), **English only!** Message deleted. (Warning: {current_warnings}/{MAX_WARNINGS_BEFORE_BAN})",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )


# ==========================================
# --- INLINE CALLBACK QUERY HANDLERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^eng_unwarn_(?P<uid>\d+)$"))
async def cb_eng_unwarn(client: Client, query: CallbackQuery):
    """Handles admin tapping the 'Unwarn' button."""
    chat_id = query.message.chat.id
    admin_id = query.from_user.id

    if not await is_user_admin(client, chat_id, admin_id):
        return await query.answer("❌ Only group administrators can use this control!", show_alert=True)

    target_id = int(query.matches[0].group("uid"))

    if target_id in USER_WARNINGS and USER_WARNINGS[target_id] > 0:
        USER_WARNINGS[target_id] = max(0, USER_WARNINGS[target_id] - 1)
        remaining = USER_WARNINGS[target_id]
        await query.answer(f"✅ Warning reduced! Remaining: {remaining}", show_alert=False)
        await query.message.edit_text(
            f"✅ **Warning cleared by admin @{query.from_user.username or query.from_user.first_name}**\n"
            f"• Target User ID: `{target_id}`\n"
            f"• Current Warnings: `{remaining}/{MAX_WARNINGS_BEFORE_BAN}`",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await query.answer("ℹ️ User has no active warnings.", show_alert=True)


@app.on_callback_query(filters.regex(r"^eng_unban_(?P<uid>\d+)$"))
async def cb_eng_unban(client: Client, query: CallbackQuery):
    """Handles admin tapping the 'Unban' button."""
    chat_id = query.message.chat.id
    admin_id = query.from_user.id

    if not await is_user_admin(client, chat_id, admin_id):
        return await query.answer("❌ Only group administrators can unban users!", show_alert=True)

    target_id = int(query.matches[0].group("uid"))

    try:
        await client.unban_chat_member(chat_id, target_id)
        if target_id in USER_WARNINGS:
            del USER_WARNINGS[target_id]
            
        await query.answer("✅ User unbanned successfully!", show_alert=True)
        await query.message.edit_text(
            f"🔓 **User Unbanned**\n"
            f"• User ID `{target_id}` has been unbanned and their warning record was reset by @{query.from_user.username or query.from_user.first_name}.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await query.answer(f"❌ Failed to unban: {e}", show_alert=True)


@app.on_callback_query(filters.regex(r"^eng_dismiss$"))
async def cb_eng_dismiss(client: Client, query: CallbackQuery):
    """Allows admins to dismiss warning alerts instantly."""
    chat_id = query.message.chat.id
    admin_id = query.from_user.id

    if not await is_user_admin(client, chat_id, admin_id):
        return await query.answer("❌ Only group administrators can dismiss this notice.", show_alert=True)

    await query.answer("Dismissed 🗑️")
    await query.message.delete()
