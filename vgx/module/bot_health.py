from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.bothealth import get_log_channel, update_log_channel

def build_health_menu(s: dict):
    en_txt = "🟢 Heartbeat: ON" if s["ping_enabled"] else "🔴 Heartbeat: OFF"
    channel_txt = f"🎯 Target: {s['log_channel_id']}" if s['log_channel_id'] else "🎯 Target: NOT SET"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(en_txt, callback_data="health_tgl")],
        [InlineKeyboardButton(channel_txt, callback_data="health_dummy")]
    ])

@Client.on_message(filters.command("sethelthlog") & filters.private)
async def set_log_cmd(client, message):
    if len(message.command) < 2:
        s = await get_log_channel()
        return await message.reply(
            "⚙️ **Bot Health Monitor**\n\n"
            "To set the target log channel, use:\n"
            "`/setlog -100123456789`",
            reply_markup=build_health_menu(s)
        )
        
    try:
        new_channel_id = int(message.command[1])
        await update_log_channel(log_channel_id=new_channel_id)
        
        s = await get_log_channel()
        await message.reply(
            "✅ **Log Channel Updated!**\nHourly heartbeat reports will be sent here.",
            reply_markup=build_health_menu(s)
        )
    except ValueError:
        await message.reply("❌ Please provide a valid numeric Channel ID.")

@Client.on_callback_query(filters.regex(r"^health_tgl$"))
async def health_toggle(client, query):
    s = await get_log_channel()
    
    if not s["log_channel_id"]:
        return await query.answer("⚠️ Please set a Log Channel ID first using /setlog!", show_alert=True)
        
    new_state = not s["ping_enabled"]
    await update_log_channel(ping_enabled=new_state)
    
    s["ping_enabled"] = new_state
    await query.message.edit_reply_markup(reply_markup=build_health_menu(s))


#============Schedule==============

import asyncio
import time
import psutil
from datetime import datetime
from config import Config

def get_readable_time(seconds: int) -> str:
    """Converts raw seconds into a readable Uptime string."""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    if d > 0:
        return f"{int(d)}d {int(h)}h {int(m)}m"
    return f"{int(h)}h {int(m)}m {int(s)}s"

async def heartbeat_loop(app):
    while True:
        try:
            settings = await get_log_channel()
            
            if settings["ping_enabled"] and settings["log_channel_id"]:
                
                # 1. Gather System Metrics
                uptime_seconds = int(time.time() - Config.BOT_START_TIME)
                bot_uptime = get_readable_time(uptime_seconds)
                
                cpu_usage = psutil.cpu_percent(interval=1)
                ram = psutil.virtual_memory()
                ram_usage = f"{ram.percent}% ({ram.used / (1024 ** 3):.2f}GB / {ram.total / (1024 ** 3):.2f}GB)"
                
                current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

                # 2. Format the Heartbeat Message
                heartbeat_msg = (
                    "💓 **Bot Health Heartbeat**\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"🟢 **Status:** Online & Active\n"
                    f"⏱ **Uptime:** `{bot_uptime}`\n"
                    f"💻 **CPU Usage:** `{cpu_usage}%`\n"
                    f"💾 **RAM Usage:** `{ram_usage}`\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"🕒 **Ping Time:** `{current_time}`"
                )
                
                # 3. Send to Private Admin Channel
                try:
                    await app.send_message(settings["log_channel_id"], heartbeat_msg)
                except Exception as e:
                    print(f"Failed to send heartbeat to {settings['log_channel_id']}: {e}")

        except Exception as e:
            print(f"Heartbeat Loop Error: {e}")
            
        # 4. Sleep for exactly 1 hour (3600 seconds)
        await asyncio.sleep(3600)
