from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputRichMessage


@Client.on_message(filters.private & filters.command("tt"))
async def stahgrt(c, m):
    await m.reply(
        "<h1>Hey i am Advanced Scheduler Bot\n</h1>"
        "Commands:\n"
        "/cmd - for my commands\n"
    )
    await c.send_rich_message(
        chat_id, InputRichMessage("<h1>Hey i am Advanced Scheduler Bot\n</h1>"),
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Data", callback_data="callbackigih_data")],
                [InlineKeyboardButton("Docs", url="https://docs.pyrogram.org")]
            ]))

