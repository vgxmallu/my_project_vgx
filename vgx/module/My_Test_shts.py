from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputRichMessage


@Client.on_message(filters.private & filters.command("tt"))
async def stahgrt(app, m):
    chat_id = m.chat.id
    message_id = m.message.id
    await m.send_rich_message(
        "<h1>Hey i am Advanced Scheduler Bot\n</h1>"
    )
    # Replace the current checklist with a new one
    await app.edit_message_checklist(
        chat_id=chat_id,
        message_id=message_id,
        checklist=types.InputChecklist(
           title="Hey i am Advanced Scheduler Bot",
           tasks=[
               types.InputChecklistTask(id=1, text="Task 1"),
               types.InputChecklistTask(id=2, text="Task 2")
           ]
       )
    )



