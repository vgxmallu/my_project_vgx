from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


@Client.on_message(filters.private & filters.command("tt"))
async def stahgrt(c, m):
    await m.reply(
        "<h1>Hey i am Advanced Scheduler Bot**\n</h1>"
        "Commands:\n"
        "/cmd - for my commands\n"
    )
