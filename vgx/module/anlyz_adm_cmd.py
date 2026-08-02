
from vgx.module.anylz_schedul import schedule_golden_msg
from vgx.database.anlys_db import profiles, db, promos, track_message, get_top_users, profiles, traffic, get_hourly_avg
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from pyrogram import Client, filters, enums
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler


# Global RAM counter: {chat_id: count}
msg_buffer = {} 

async def check_viral_spikes(app):
    for chat_id, count in msg_buffer.items():
        if await is_viral_moment(chat_id, count):
            promo = await promos.find_one({"chat_id": chat_id})
            if promo:
                await app.send_message(chat_id, f"🔥 **TRENDING NOW:**\n\n{promo['text']}")
                # Cooldown logic needed here to prevent spam
    
    msg_buffer.clear() # Reset every 5 mins


async def get_golden_hour(chat_id):
    # Find the hour with highest historical activity
    cursor = traffic.find({"chat_id": chat_id}).sort("count", -1).limit(1)
    result = await cursor.to_list(length=1)
    return result[0]["hour"] if result else 9 # Default to 9 AM if no data

async def is_viral_moment(chat_id, current_msgs_last_5_min):
    # 1. Get average for this current hour
    hour = time.localtime().tm_hour
    historical_total = await get_hourly_avg(chat_id, hour)
    
    # Assume historical_total is total over 7 days.
    # Avg per 5 mins = (Total / 7 days) / (60/5 slots)
    # Simplified Logic:
    expected_rate = (historical_total / 7) / 12 
    
    # Avoid div by zero or low data noise
    if expected_rate < 5: return False 

    # 2. Compare
    if current_msgs_last_5_min > (expected_rate * 1.5):
        return True
    return False


@Client.on_message(filters.command("schedule_best") & filters.group)
async def cmd_sched(c, m):
    # Usage: /schedule_best This is my message
    if len(m.command) < 2:
        return await m.reply("Usage: `/schedule_best [message]`")
    
    text = m.text.split(None, 1)[1]
    time_str = await schedule_golden_msg(c, m.chat.id, text)
    
    await m.reply(f"📅 **Scheduled!**\nBased on your traffic, this will post at: `{time_str}` (Golden Hour)")

@Client.on_message(filters.command("set_viral_promo") & filters.group)
async def set_promo(c, m):
    # Saves a message to be used when viral spike is detected
    if not m.reply_to_message:
        return await m.reply("Reply to the message you want to auto-post during viral spikes.")
    
    # Save the ID/Text
    await promos.update_one(
        {"chat_id": m.chat.id}, 
        {"$set": {"text": m.reply_to_message.text or "Promo!"}}, 
        upsert=True
    )
    await m.reply("🔥 **Viral Promo Set!** If chat goes crazy, I'll post this.")


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
    text += f"⚡ **This week's messages:** `{total_week}`\n\n"
    
    # List Body
    for rank, user in enumerate(top, 1):
        name = user['name']
        # Name Truncation logic
        if len(name) > 12:
            name = name[:12] + ".."
        
        # Formatting: Rank. Name — Count ✉️
        text += f"{rank}. **{name}** — `{user['messages']}` ✉️\n"
    
    text += "\n📈 **Keep chatting to reach the top!**"
    
    # 1-2-1 Button Layout
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 Group Overall", callback_data="lb_all")],
        [
            InlineKeyboardButton("📅 Today", callback_data="lb_today"),
            InlineKeyboardButton("🗓 Week", callback_data="lb_week")
        ],
        [InlineKeyboardButton("🌍 Global Ranking", callback_data="lb_global")]
    ])
    
    await m.reply(text, reply_markup=kb)


#====================================================

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


scheduler = AsyncIOScheduler()

async def schedule_golden_msg(app, chat_id, text):
    peak_hour = await get_golden_hour(chat_id)
    
    now = datetime.now()
    run_date = now.replace(hour=peak_hour, minute=0, second=0)
    
    # If peak hour passed today, schedule for tomorrow
    if run_date < now:
        run_date += timedelta(days=1)
    
    scheduler.add_job(
        send_msg, 
        "date", 
        run_date=run_date, 
        args=[app, chat_id, text]
    )
    return run_date.strftime("%Y-%m-%d %H:%M")

async def send_msg(app, chat_id, text):
    try:
        await app.send_message(chat_id, text)
    except Exception as e:
        print(f"Failed to send scheduled msg: {e}")

def start_anlyz_scheduler():
    if not scheduler.running:
        scheduler.start()
