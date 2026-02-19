from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.anlys_db import track_message, get_top_users, profiles

@Client.on_message(filters.group & ~filters.bot, group=1)
async def watcher(c, m):
    # This runs on EVERY message to build data
    await track_message(m.chat.id, m.from_user.id, m.from_user.first_name)

@Client.on_message(filters.command("leaderboard") & filters.group)
async def lb_handler(c, m):
    top = await get_top_users(m.chat.id)
    if not top:
        return await m.reply("📉 Not enough data yet.")

    # Calculate "This week's messages" (Total of top 10 for demo)
    total_week = sum(u['messages'] for u in top)
    
    # Header
    text = f"👤 **Member Leaderboard**\n"
    text += f"⚡ *This week's messages: {total_week}*\n\n"
    
    # List Body
    for rank, user in enumerate(top, 1):
        name = user['name']
        # Name Truncation logic
        if len(name) > 12:
            name = name[:12] + ".."
        
        # Formatting: Rank. Name — Count ✉️
        text += f"{rank}. **{name}** — `{user['messages']}` ✉️\n"
    
    text += "\n📈 *Keep chatting to reach the top!*"
    
    # 1-2-1 Button Layout
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 Overall", callback_data="lb_all")],
        [
            InlineKeyboardButton("📅 Today", callback_data="lb_today"),
            InlineKeyboardButton("🗓 Week", callback_data="lb_week")
        ],
        [InlineKeyboardButton("💤My Channel", url="https://t.me/xbots_x")]
    ])
    
    await m.reply(text, reply_markup=kb)
