import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app

API_URL = "https://whatthecommit.com/index.txt"


async def fetch_commit_message() -> str:
    """Fetches a random humorous commit message from whatthecommit.com."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(API_URL)
            if response.status_code == 200:
                return response.text.strip()
        except Exception:
            pass
    return "Fix bug that I have no idea why it happened."


def get_commit_menu() -> InlineKeyboardMarkup:
    """Interactive inline keyboard dashboard for Commit controls."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏮️ Previous", callback_data="cmt_prev"),
            InlineKeyboardButton("🎲 Random", callback_data="cmt_random"),
            InlineKeyboardButton("⏭️ Next", callback_data="cmt_next")
        ],
        [
            InlineKeyboardButton("📚 WhatTheCommit Docs", url="https://whatthecommit.com/"),
            InlineKeyboardButton("❌ Close", callback_data="cmt_close")
        ]
    ])


# ==========================================
# --- COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.command(["commit", "whatthecommit", "gitcommit"]))
async def cmd_commit_dashboard(client: Client, message: Message):
    """Command: /commit - Generates a sarcastic/hilarious git commit message."""
    msg = await message.reply_text("💻 Generating commit message...")
    
    commit_msg = await fetch_commit_message()

    response_text = (
        f"💻 **WHAT THE COMMIT?**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"```bash\n"
        f"git commit -m \"{commit_msg}\"\n"
        f"```\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await message.reply_text(response_text, reply_markup=get_commit_menu(), parse_mode=ParseMode.MARKDOWN)
    await msg.delete()


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^cmt_(?P<action>random|next|prev)$"))
async def cb_commit_controls(client: Client, query: CallbackQuery):
    action = query.matches[0].group("action")
    await query.answer(f"Fetching {action} commit...")

    commit_msg = await fetch_commit_message()

    response_text = (
        f"💻 **WHAT THE COMMIT?**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"```bash\n"
        f"git commit -m \"{commit_msg}\"\n"
        f"```\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    try:
        await query.message.edit_text(response_text, reply_markup=get_commit_menu(), parse_mode=ParseMode.MARKDOWN)
    except Exception:
        # Ignore if content is identical
        pass


@app.on_callback_query(filters.regex(r"^cmt_close$"))
async def cb_cmt_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
