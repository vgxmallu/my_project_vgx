import httpx
from pyrogram import Client, filters
from pyrogram.types import (
    Message, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery, 
    InputMediaAnimation
)
from pyrogram.enums import ParseMode
from vgx import app

API_URL = "https://yesno.wtf/api"


async def fetch_yesno_data() -> dict:
    """Fetches a random yes/no decision and GIF from yesno.wtf API."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(API_URL)
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "maybe").upper()
                
                # Assign status indicators & emojis
                if answer == "YES":
                    emoji = "🟢"
                elif answer == "NO":
                    emoji = "🔴"
                else:
                    emoji = "🟡"

                return {
                    "success": True,
                    "answer": answer,
                    "emoji": emoji,
                    "image": data.get("image")
                }
        except Exception:
            pass
            
    return {"success": False}


def get_yesno_menu() -> InlineKeyboardMarkup:
    """Interactive inline keyboard dashboard for YesNo controls."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏮️ Previous", callback_data="yn_prev"),
            InlineKeyboardButton("🎲 Random", callback_data="yn_random"),
            InlineKeyboardButton("⏭️ Next", callback_data="yn_next")
        ],
        [
            InlineKeyboardButton("📚 API Docs", url="https://yesno.wtf/api"),
            InlineKeyboardButton("❌ Close", callback_data="yn_close")
        ]
    ])


# ==========================================
# --- COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.command(["yesno", "decision", "ask"]))
async def cmd_yesno_dashboard(client: Client, message: Message):
    """Command: /yesno - Opens the interactive Yes/No decision engine."""
    msg = await message.reply_text("🤔 Consulting the oracle...")
    
    data = await fetch_yesno_data()
    if not data["success"]:
        return await msg.edit_text("❌ Failed to reach YesNo API. Please try again later.")

    caption = (
        f"🔮 **ORACLE DECISION ENGINE**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Verdict:** {data['emoji']} `{data['answer']}`\n"
        f"• **Source API:** `yesno.wtf/api`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await message.reply_animation(
        animation=data["image"],
        caption=caption,
        reply_markup=get_yesno_menu(),
        parse_mode=ParseMode.MARKDOWN
    )
    await msg.delete()


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^yn_(?P<action>random|next|prev)$"))
async def cb_yesno_controls(client: Client, query: CallbackQuery):
    action = query.matches[0].group("action")
    await query.answer(f"Fetching {action} decision...")

    data = await fetch_yesno_data()
    if not data["success"]:
        return await query.answer("Failed to fetch new decision.", show_alert=True)

    caption = (
        f"🔮 **ORACLE DECISION ENGINE**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Verdict:** {data['emoji']} `{data['answer']}`\n"
        f"• **Action Triggered:** `{action.capitalize()}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    try:
        # Edit existing message media (updates the GIF and caption smoothly)
        await query.message.edit_media(
            media=InputMediaAnimation(media=data["image"], caption=caption, parse_mode=ParseMode.MARKDOWN),
            reply_markup=get_yesno_menu()
        )
    except Exception:
        # Fallback if media edit fails
        await query.message.delete()
        await query.message.reply_animation(
            animation=data["image"],
            caption=caption,
            reply_markup=get_yesno_menu(),
            parse_mode=ParseMode.MARKDOWN
        )


@app.on_callback_query(filters.regex(r"^yn_close$"))
async def cb_yn_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
