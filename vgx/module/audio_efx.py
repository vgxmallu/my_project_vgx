from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

def get_audio_effects_keyboard():
    """Builds the audio processing UI exactly as referenced."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔊 SLOWED", callback_data="fx_slowed"),
            InlineKeyboardButton("🎵 REVERB", callback_data="fx_reverb")
        ],
        [
            InlineKeyboardButton("🔊 SLOW + REV", callback_data="fx_slowrev")
        ],
        [
            InlineKeyboardButton("🔊 8D", callback_data="fx_8d"),
            InlineKeyboardButton("🎵 CONCERT", callback_data="fx_concert")
        ],
        [
            InlineKeyboardButton("🔊 BASS", callback_data="fx_bass"),
            InlineKeyboardButton("🎵 NIGHTCORE", callback_data="fx_nightcore")
        ],
        [
            InlineKeyboardButton("⚙️ MORE", callback_data="fx_more")
        ]
    ])

@Client.on_message(filters.command("audio") & filters.private)
async def send_audio_ui(client: Client, message: Message):
    # Sends the text and UI matching the image reference
    text = "✨ @X_BOTSX | INFO"
    
    await message.reply_text(
        text,
        reply_markup=get_audio_effects_keyboard()
    )


import os
import asyncio
from pyrogram.types import CallbackQuery

@Client.on_callback_query(filters.regex(r"^fx_(slowed|reverb|slowrev|8d|concert|bass|nightcore|more)$"))
async def handle_audio_effect(client: Client, query: CallbackQuery):
    effect = query.matches[0].group(1)
    
    if effect == "more":
        return await query.answer("Opening settings...", show_alert=True)

    # 1. Navigate Telegram's reply chain to find the actual media file
    cmd_msg = query.message.reply_to_message
    audio_msg = None

    if cmd_msg:
        if cmd_msg.audio or cmd_msg.voice:
            # The bot replied directly to the audio
            audio_msg = cmd_msg
        elif cmd_msg.reply_to_message and (cmd_msg.reply_to_message.audio or cmd_msg.reply_to_message.voice):
            # The bot replied to the /audio command, which replied to the audio
            audio_msg = cmd_msg.reply_to_message

    if not audio_msg:
        await query.answer("Audio not found!", show_alert=True)
        return await query.edit_message_text("❌ Could not find the audio file. Please reply to an audio message with `/audio`.")

    await query.answer(f"Applying {effect.upper()}...")
    await query.edit_message_text(f"⏳ **Processing {effect.upper()} effect...**")

    # 2. Download the correctly identified audio file
    input_path = await audio_msg.download()
    output_path = f"processed_{effect}.mp3"

    # 3. FFmpeg commands for audio filters
    ffmpeg_cmd = []
    if effect == "slowed":
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", input_path, "-filter:a", "atempo=0.8", output_path]
    elif effect == "nightcore":
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", input_path, "-filter:a", "asetrate=44100*1.25,atempo=1.0", output_path]
    elif effect == "bass":
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", input_path, "-af", "equalizer=f=60:width_type=h:width=50:g=10", output_path]
    else:
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", input_path, "-filter:a", "atempo=0.9", output_path]

    # 4. Execute FFmpeg asynchronously
    proc = await asyncio.create_subprocess_exec(*ffmpeg_cmd)
    await proc.communicate()

    # 5. Send back the processed audio track
    await client.send_audio(
        chat_id=query.message.chat.id,
        audio=output_path,
        caption=f"✨ **Effect Applied:** `{effect.upper()}`\n👤 @AartiMusic"
    )

    # 6. Clean up local temporary files
    if os.path.exists(input_path): os.remove(input_path)
    if os.path.exists(output_path): os.remove(output_path)
