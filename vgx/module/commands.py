from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from utils import get_settings_keyboard

# In-memory session for the setup process
user_sessions = {}


@Client.on_message(filters.command("gstart"))
async def start_handler(client, message):
    await message.reply(
        "👋 **Welcome to the Group Scheduler Bot!**\n\n"
        "I can schedule messages, repeat them automatically, pin them, "
        "and manage your group announcements.\n\n"
        "🛠 **Commands:**\n"
        "• /schedule - Create a new scheduled post\n"
        "• /myjobs - View active schedules\n\n"
        "ℹ️ *Add me to your group as Admin first!*"
    )
    

@Client.on_message(filters.command("start"))
async def start(client, message):
    await message.reply("👋 **Advanced Scheduler Bot**\n\nUse /create to start building a new scheduled post!")

@Client.on_message(filters.command("create"))
async def create_post(client, message):
    chat_id = message.chat.id
    user_sessions[chat_id] = {
        "text": None,
        "media": None,
        "pin": False,
        "preview": True,
        "repeat": 0,
        "night_mode": False,
        "schedule_time": None,
        "step": "waiting_content"
    }
    
    await message.reply(
        "📝 **Create Scheduled Message**\n\nPlease send me the **Text** or **Photo**.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
    )

@Client.on_message(filters.text | filters.photo | filters.video)
async def handle_content(client, message: Message):
    chat_id = message.chat.id
    if chat_id not in user_sessions:
        return

    session = user_sessions[chat_id]
    
    if session["step"] == "waiting_content":
        session["text"] = message.text or message.caption or ""
        session["media"] = message.photo.file_id if message.photo else (message.video.file_id if message.video else None)
        session["media_type"] = "photo" if message.photo else ("video" if message.video else "text")
        session["step"] = "menu"
        
        await message.reply(
            "⚙️ **Configure Settings**",
            reply_markup=get_settings_keyboard(session)
        )
