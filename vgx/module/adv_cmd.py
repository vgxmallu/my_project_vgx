from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.db_advanc import db

@Client.on_message(filters.private & filters.command("start"))
async def start(c, m):
    await m.reply(
        "🤖 **Advanced Scheduler Bot**\n\n"
        "Features:\n"
        "✅ Auto-Repeat (5m, 10m, 1h...)\n"
        "✅ Auto-Delete & Pin\n"
        "✅ Delete Previous Message\n"
        "✅ Supports Photo/Video/Text\n\n"
        "Commands:\n"
        "/schedule - New Schedule\n"
        "/myjobs - Manage Schedules"
    )

@Client.on_message(filters.private & filters.command("myjobs"))
async def list_jobs(c, m):
    jobs = await db.get_user_jobs(m.from_user.id)
    btn_list = []
    async for j in jobs:
        status = "⏸" if j.get('paused') else "▶️"
        chat = str(j.get('target_chat'))[:10]
        btn_list.append([
            InlineKeyboardButton(
                f"{status} {chat} | {j.get('interval', 0)}m", 
                callback_data=f"mngr_view_{j['_id']}"
            )
        ])
    
    if not btn_list:
        return await m.reply("📭 No active schedules found.")
        
    await m.reply("📋 **Your Scheduled Jobs:**", reply_markup=InlineKeyboardMarkup(btn_list))
