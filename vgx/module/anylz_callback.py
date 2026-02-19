from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.anlys_db import profiles, db # Ensure db is imported to access other collections
import time
from datetime import datetime, timedelta

@Client.on_callback_query(filters.regex("^lb_"))
async def leaderboard_callback_handler(c, q):
    chat_id = q.message.chat.id
    data = q.data.split("_")[1] # Extract 'all', 'today', or 'week'
    
    # 1. Determine the query and header based on timeframe
    # Note: For 'today' and 'week', you'd ideally have a field like 'last_active' 
    # or a separate 'daily_stats' collection.
    
    if data == "all":
        title = "🏆 Overall"
        # Fetching top 10 lifetime
        top_users = await profiles.find({"chat_id": chat_id}).sort("messages", -1).limit(10).to_list(length=10)
    
    elif data == "today":
        title = "📅 Today"
        # Simplified: Querying users active in the last 24 hours
        # In a real app, you'd store daily_messages in a separate doc
        day_ago = time.time() - 86400
        top_users = await profiles.find({
            "chat_id": chat_id, 
            "last_active": {"$gte": day_ago}
        }).sort("messages", -1).limit(10).to_list(length=10)

    elif data == "week":
        title = "🗓 Week"
        week_ago = time.time() - (86400 * 7)
        top_users = await profiles.find({
            "chat_id": chat_id, 
            "last_active": {"$gte": week_ago}
        }).sort("messages", -1).limit(10).to_list(length=10)

    # 2. Build the updated text
    if not top_users:
        return await q.answer("📉 No data for this timeframe yet.", show_alert=True)

    total_msgs = sum(u.get('messages', 0) for u in top_users)
    
    text = f"👤 **Member Leaderboard** ({title})\n"
    text += f"⚡ **Messages in this view: {total_msgs}**\n\n"
    
    for rank, user in enumerate(top_users, 1):
        name = user.get('name', 'Unknown')
        if len(name) > 12:
            name = name[:12] + ".."
        text += f"{rank}. **{name}** — `{user.get('messages', 0)}` ✉️\n"
    
    text += "\n📈 **Keep chatting to reach the top!**"

    # 3. Keep the same 1-2-1 button layout
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 Overall", callback_data="lb_all")],
        [
            InlineKeyboardButton("📅 Today", callback_data="lb_today"),
            InlineKeyboardButton("🗓 Week", callback_data="lb_week")
        ],
        [InlineKeyboardButton("🌍 Global Ranking", callback_data="lb_global")]
    ])

    # 4. Edit the message (Avoid editing if the content is identical to prevent errors)
    try:
        await q.edit_message_text(text, reply_markup=kb)
    except Exception as e:
        # This usually happens if the user clicks the same button twice
        await q.answer("Done!")


@Client.on_callback_query(filters.regex("^lb_global"))
async def global_lb_callback(c, q):
    # 1. Fetch data using the aggregation function
    from database import get_global_users
    top_users = await get_global_users(limit=10)
    
    if not top_users:
        return await q.answer("❌ No global data found.")

    # 2. Build the text
    text = "🌍 **Global Top 10 Leaderboard**\n"
    text += "**(Activity across all groups)**\n\n"
    
    for rank, user in enumerate(top_users, 1):
        name = user.get('name', 'User')
        if len(name) > 12:
            name = name[:12] + ".."
        
        # Note: We use 'total_messages' here because of the aggregation field name
        count = user.get('total_messages', 0)
        text += f"{rank}. **{name}** — `{count}` ✉️\n"
    
    text += "\n📈 **Are you the king of the network?**"

    # 3. Use a "Back" button to return to group stats
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Group Stats", callback_data="lb_all")],
        [InlineKeyboardButton("↪️ Full Leaderboard", url="https://t.me/Xbots_x")]
    ])

    await q.edit_message_text(text, reply_markup=kb)
    
