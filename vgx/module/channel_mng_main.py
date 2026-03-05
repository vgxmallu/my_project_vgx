from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.channel_db import get_user

def build_dashboard_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ Create Post", callback_data="chm_create_post"),
         InlineKeyboardButton("📚 Multipost", callback_data="chm_multipost")],
        [InlineKeyboardButton("⚙️ Channel Settings", callback_data="chm_select_channel")],
        [InlineKeyboardButton("🪧 Service Messages", callback_data="chm_service_msgs"),
         InlineKeyboardButton("📋 Auto-complete", callback_data="chm_autocomplete")],
        [InlineKeyboardButton("🏃‍♂️ Welcome/Goodbye", callback_data="chm_welcome_goodbye")],
        [InlineKeyboardButton("🌎 Time Zone", callback_data="chm_set_timezone"),
         InlineKeyboardButton("📤 Forward (PLUS ⭐️)", callback_data="chm_forwarding")]
    ])

@Client.on_message(filters.command("channel") & filters.private)
async def start_cjhmd(client, message):
    user = await get_user(message.from_user.id)
    tz = user.get("timezone", "UTC")
    
    text = (
        "👋 **Welcome to the Advanced Channel Manager!**\n\n"
        "Manage your channels, schedule posts with rich media and inline buttons, "
        "and track user reactions all in one place.\n\n"
        f"🌍 **Your Timezone:** `{tz}`\n"
        "👇 *Select an option below to get started:*"
    )
    await message.reply(text, reply_markup=build_dashboard_menu())

@Client.on_callback_query(filters.regex(r"^chm_main_menu$"))
async def back_to_main(client, query):
    await query.message.edit_text("👇 *Main Menu*", reply_markup=build_dashboard_menu())
