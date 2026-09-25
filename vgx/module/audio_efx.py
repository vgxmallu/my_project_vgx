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
import subprocess
from pyrogram.types import CallbackQuery

@Client.on_callback_query(filters.regex(r"^fx_(slowed|reverb|slowrev|8d|concert|bass|nightcore|more)$"))
async def handle_audio_effect(client: Client, query: CallbackQuery):
    effect = query.matches[0].group(1)
    
    if effect == "more":
        return await query.answer("Opening settings...", show_alert=True)

    await query.answer(f"Applying {effect.upper()}...")
    
    # Check if the message has a replied-to audio file
    reply_msg = query.message.reply_to_message
    if not reply_msg or not (reply_msg.audio or reply_msg.voice):
        return await query.edit_message_text("❌ Please reply to an audio file with `/audio` first!")

    await query.edit_message_text(f"⏳ **Processing {effect.upper()} effect...**")

    # 1. Download input file
    input_path = await reply_msg.download()
    output_path = f"processed_{effect}.mp3"

    # 2. FFmpeg commands for audio filters
    ffmpeg_cmd = []
    if effect == "slowed":
        # Slow down audio playback speed (0.8x)
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", input_path, "-filter:a", "atempo=0.8", output_path]
    elif effect == "nightcore":
        # Speed up audio (1.25x) and increase pitch
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", input_path, "-filter:a", "asetrate=44100*1.25,atempo=1.0", output_path]
    elif effect == "bass":
        # Boost bass frequencies
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", input_path, "-af", "equalizer=f=60:width_type=h:width=50:g=10", output_path]
    else:
        # Default fallback
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", input_path, "-filter:a", "atempo=0.9", output_path]

    # 3. Execute FFmpeg asynchronously
    proc = await asyncio.create_subprocess_exec(*ffmpeg_cmd)
    await proc.communicate()

    # 4. Send back the processed audio track
    await client.send_audio(
        chat_id=query.message.chat.id,
        audio=output_path,
        caption=f"✨ **Effect Applied:** `{effect.upper()}`\n👤 @AartiMusic"
    )

    # Clean up local temporary files
    if os.path.exists(input_path): os.remove(input_path)
    if os.path.exists(output_path): os.remove(output_path)
