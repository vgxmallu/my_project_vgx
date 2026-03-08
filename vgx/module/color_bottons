from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ButtonStyle
# ... your client setup ...

@Client.on_message(filters.command("colors"))
async def send_colored_grid(client, message):
    
    # 1. Define the colored buttons
    # You can add the new 'style' parameter to set their colors
    btn_green = InlineKeyboardButton("Green Button", url="https://t.me/your_bot", icon_custom_emoji_id=5355142851615283756, style=ButtonStyle.SUCCESS)
    btn_blue = InlineKeyboardButton("Blue Button", url="https://t.me/your_bot", icon_custom_emoji_id=5440389890787281213,  style=ButtonStyle.PRIMARY)
    btn_red = InlineKeyboardButton("Red Button", url="https://t.me/your_bot", icon_custom_emoji_id=5354968347094046619, style=ButtonStyle.DANGER)

    # 2. Create the grid layout just like your image
    keyboard = InlineKeyboardMarkup([
        [btn_green, btn_blue, btn_red], # Row 1: Green, Blue, Red
        [btn_green, btn_blue, btn_red], # Row 2: Green, Blue, Red
        [btn_green, btn_blue, btn_red]  # Row 3: Green, Blue, Red
    ])

    text = "🌈 **Here are your colored buttons!**"
    
    await message.reply(text, reply_markup=keyboard)


