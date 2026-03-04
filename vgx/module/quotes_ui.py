from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
import database as db
from config import Config 

def get_menu_text_and_keyboard(data: dict):
    """Generates dynamic keyboard based on current DB state."""
    status = "🟢 Enabled" if data["enabled"] else "🔴 Disabled"
    
    # Reverse lookup for display names
    interval_name = [k for k, v in Config.INTERVALS.items() if v == data["interval"]][0]
    delete_name = [k for k, v in Config.DELETE_TIMES.items() if v == data["auto_delete"]][0]
    pin_status = "✅ On" if data["pin"] else "❌ Off"

    text = (
        "**⚙️ Quote Scheduler Settings**\n\n"
        f"**Status:** {status}\n"
        f"**Interval:** {interval_name}\n"
        f"**Auto-Delete:** {delete_name}\n"
        f"**Pin Messages:** {pin_status}\n\n"
        "Use the buttons below to configure:"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Turn {'OFF' if data['enabled'] else 'ON'}", callback_data="toggle_status")],
        [InlineKeyboardButton(f"⏱ Interval: {interval_name}", callback_data="cycle_interval")],
        [InlineKeyboardButton(f"🗑 Auto-Del: {delete_name}", callback_data="cycle_delete")],
        [InlineKeyboardButton(f"📌 Pinning: {pin_status}", callback_data="toggle_pin")],
        [InlineKeyboardButton("🎯 Target a Group", callback_data="target_group")],
        [InlineKeyboardButton("🧹 Delete Last Quote", callback_data="delete_last")]
    ])
    return text, kb

@Client.on_message(filters.command("quotes"))
async def quotes_menu(client: Client, message: Message):
    # This works in both Private Messages and Groups
    chat_id = message.chat.id
    data = await db.get_chat(chat_id)
    text, kb = get_menu_text_and_keyboard(data)
    await message.reply_text(text, reply_markup=kb)

@Client.on_message(filters.command("target") & filters.private)
async def add_target_group(client: Client, message: Message):
    """Allows users to map a group ID from PM."""
    if len(message.command) < 2:
        return await message.reply("Please provide a Group ID. Example: `/target -100123456789`")
    
    try:
        target_id = int(message.command[1])
        # Initialize the target group in DB
        data = await db.get_chat(target_id)
        text, kb = get_menu_text_and_keyboard(data)
        await message.reply(f"Settings for Target Group `{target_id}`:", reply_markup=kb)
    except ValueError:
        await message.reply("Invalid ID format.")

@Client.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    # Determine which chat ID we are modifying. 
    # If it's a target group menu sent in PM, we extract the ID from the text.
    if "Target Group" in query.message.text:
        chat_id = int(query.message.text.split("`")[1])
    else:
        chat_id = query.message.chat.id

    data = await db.get_chat(chat_id)
    action = query.data

    if action == "toggle_status":
        data["enabled"] = not data["enabled"]
    
    elif action == "cycle_interval":
        keys = list(INTERVALS.keys())
        current_idx = keys.index([k for k, v in INTERVALS.items() if v == data["interval"]][0])
        next_idx = (current_idx + 1) % len(keys)
        data["interval"] = INTERVALS[keys[next_idx]]

    elif action == "cycle_delete":
        keys = list(DELETE_TIMES.keys())
        current_idx = keys.index([k for k, v in DELETE_TIMES.items() if v == data["auto_delete"]][0])
        next_idx = (current_idx + 1) % len(keys)
        data["auto_delete"] = DELETE_TIMES[keys[next_idx]]

    elif action == "toggle_pin":
        data["pin"] = not data["pin"]
        
    elif action == "target_group":
        return await query.answer("Send /target <group_id> in this chat to configure a group from your PM!", show_alert=True)

    elif action == "delete_last":
        last_id = data.get("last_msg_id")
        if last_id:
            try:
                await client.delete_messages(chat_id, last_id)
                await db.update_chat(chat_id, last_msg_id=None)
                return await query.answer("Last quote deleted successfully!", show_alert=True)
            except Exception:
                return await query.answer("Failed to delete. Message might be too old or already deleted.", show_alert=True)
        else:
            return await query.answer("No recent quote found in database.", show_alert=True)

    # Save updates and refresh UI
    await db.update_chat(chat_id, **data)
    text, kb = get_menu_text_and_keyboard(data)
    
    try:
        await query.message.edit_text(text, reply_markup=kb)
    except MessageNotModified:
        pass
