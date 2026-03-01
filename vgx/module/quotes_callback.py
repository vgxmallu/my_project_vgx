from pyrogram import filters
from pyrogram.types import CallbackQuery

from vgx.database.quets_db2 import settings_col
from utils.keyboards import main_menu, interval_menu, autodel_menu
from scheduler import schedule_job_for_chat, remove_job_for_chat, scheduler
from vgx import app

# Enable / Disable
@app.on_callback_query(filters.regex(r"^(enable|disable)\|\-?\d+$"))
async def toggle_enable(_, cq: CallbackQuery):
    action, chat_s = cq.data.split("|")
    chat_id = int(chat_s)
    enabled = action == "enable"
    await settings_col.update_one({"chat_id": chat_id}, {"$set": {"enabled": enabled}}, upsert=True)

    # schedule or remove job depending on interval
    doc = await settings_col.find_one({"chat_id": chat_id})
    interval = doc.get("interval")
    if enabled and interval:
        schedule_job_for_chat(chat_id, int(interval))
    else:
        remove_job_for_chat(chat_id)

    await cq.answer("Updated!")
    await cq.message.edit_text("🌸 Random Quotes Scheduler — Control Panel", reply_markup=main_menu(chat_id))


# Show interval choices
@app.on_callback_query(filters.regex(r"^intervals\|\-?\d+$"))
async def open_intervals(_, cq: CallbackQuery):
    chat_id = int(cq.data.split("|")[1])
    await cq.message.edit_text("⏰ Choose an interval:", reply_markup=interval_menu(chat_id))
    await cq.answer()

# Set interval and schedule job
@app.on_callback_query(filters.regex(r"^setint\|\-?\d+\|\d+$"))
async def set_interval(_, cq: CallbackQuery):
    _, chat_s, sec_s = cq.data.split("|")
    chat_id = int(chat_s); seconds = int(sec_s)
    await settings_col.update_one({"chat_id": chat_id}, {"$set": {"interval": seconds}}, upsert=True)
    # if enabled, schedule
    doc = await settings_col.find_one({"chat_id": chat_id})
    if doc.get("enabled"):
        schedule_job_for_chat(chat_id, seconds)
    await cq.answer(f"Interval set to {seconds} seconds.")
    await cq.message.edit_text("🌸 Random Quotes Scheduler — Control Panel", reply_markup=main_menu(chat_id))

# Open auto-delete menu
@app.on_callback_query(filters.regex(r"^autodels\|\-?\d+$"))
async def open_autodel(_, cq: CallbackQuery):
    chat_id = int(cq.data.split("|")[1])
    await cq.message.edit_text("🗑 Choose auto-delete:", reply_markup=autodel_menu(chat_id))
    await cq.answer()

# Set auto-delete seconds
@app.on_callback_query(filters.regex(r"^setdel\|\-?\d+\|\d+$"))
async def set_autodel(_, cq: CallbackQuery):
    _, chat_s, sec_s = cq.data.split("|")
    chat_id = int(chat_s); seconds = int(sec_s)
    await settings_col.update_one({"chat_id": chat_id}, {"$set": {"auto_delete": seconds}}, upsert=True)
    await cq.answer(f"Auto-delete set to {seconds}s")
    await cq.message.edit_text("🌸 Random Quotes Scheduler — Control Panel", reply_markup=main_menu(chat_id))

# Toggle delete-last
@app.on_callback_query(filters.regex(r"^dellast\|\-?\d+$"))
async def toggle_delete_last(_, cq: CallbackQuery):
    chat_id = int(cq.data.split("|")[1])
    doc = await settings_col.find_one({"chat_id": chat_id}) or {}
    new_state = not doc.get("delete_last", False)
    await settings_col.update_one({"chat_id": chat_id}, {"$set": {"delete_last": new_state}}, upsert=True)
    await cq.answer("Delete-last toggled!")
    await cq.message.edit_text("🌸 Random Quotes Scheduler — Control Panel", reply_markup=main_menu(chat_id))

# Toggle pin
@app.on_callback_query(filters.regex(r"^pin\|\-?\d+$"))
async def toggle_pin(_, cq: CallbackQuery):
    chat_id = int(cq.data.split("|")[1])
    doc = await settings_col.find_one({"chat_id": chat_id}) or {}
    new_state = not doc.get("pin", False)
    await settings_col.update_one({"chat_id": chat_id}, {"$set": {"pin": new_state}}, upsert=True)
    await cq.answer("Pin toggled!")
    await cq.message.edit_text("🌸 Random Quotes Scheduler — Control Panel", reply_markup=main_menu(chat_id))

# Info for target (button leads to instruction - setting target requires /settarget command)
@app.on_callback_query(filters.regex(r"^target_info\|\-?\d+$"))
async def target_info(_, cq: CallbackQuery):
    chat_id = int(cq.data.split("|")[1])
    await cq.answer("To set target chat use /settarget <chat_id>. This is required because target needs a numeric id.", show_alert=True)

# Show current settings
@app.on_callback_query(filters.regex(r"^show\|\-?\d+$"))
async def show_settings(_, cq: CallbackQuery):
    chat_id = int(cq.data.split("|")[1])
    doc = await settings_col.find_one({"chat_id": chat_id}) or {}
    text = [
        f"Chat ID: {chat_id}",
        f"Enabled: {doc.get('enabled', False)}",
        f"Interval: {doc.get('interval', 'None')}",
        f"Auto-delete: {doc.get('auto_delete', 0)}s",
        f"Delete-last: {doc.get('delete_last', False)}",
        f"Pin: {doc.get('pin', False)}",
        f"Target: {doc.get('target_chat', 'None')}"
    ]
    await cq.answer("\n".join(text), show_alert=True)
