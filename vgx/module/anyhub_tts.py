import os
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config  # Must contain APY_TOKEN

# --- CONFIGURATION & ENDPOINT ---
TTS_FILE_URL = "https://api.eu.apyhub.com/apyhub/convert-text-to-speech/file/file"

def get_apy_token() -> str:
    """Retrieves the ApyHub token from config safely."""
    return getattr(Config, "APY_HUB_TOKEN", None)


# --- APYHUB TTS FILE HELPER ---

async def convert_file_to_speech(file_path: str, gender: str = "female") -> bytes:
    """Uploads a document file to ApyHub and returns the generated MP3 binary data."""
    token = get_apy_token()
    if not token:
        return None

    headers = {"apy-token": token}
    data = {"gender": gender.lower()}
    
    async with httpx.AsyncClient() as client:
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                # Increased timeout for file upload & synthesis generation
                resp = await client.post(TTS_FILE_URL, data=data, files=files, headers=headers, timeout=60.0)
                
                if resp.status_code == 200:
                    return resp.content  # Returns binary MP3 data bytes
                
                print(f"ApyHub TTS Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"ApyHub TTS Exception: {e}")
        return None


# --- COMMAND & FILE HANDLER ---

@app.on_message(filters.command(["ttsdialog", "ttsfile", "texttospeech"]) | filters.document)
async def handle_tts_file(client: Client, message: Message):
    """
    Handles document uploads or text commands to convert documents 
    (.txt, .pdf, etc.) into MP3 speech audio via ApyHub.
    """
    token = get_apy_token()
    if not token:
        return await message.reply_text("❌ Missing `APY_TOKEN` in your `config.py`.")

    # Check if user sent a document file
    doc = message.document
    if not doc and message.command:
        return await message.reply_text(
            "⚠️ **Usage Instructions:**\n\n"
            "Reply to or upload a document file (`.txt`, `.pdf`, etc.) with the caption:\n"
            "`/ttsfile [male/female]`\n\n"
            "_Example:_ Upload a text file and type `/ttsfile male`",
            parse_mode=ParseMode.MARKDOWN
        )

    target_doc = doc or message.document
    if not target_doc:
        return await message.reply_text("⚠️ Please attach a valid document file to convert into speech.")

    # Extract optional gender preference from caption/args (default: female)
    gender = "female"
    if message.caption:
        parts = message.caption.strip().split()
        if len(parts) > 1 and parts[1].lower() in ["male", "female"]:
            gender = parts[1].lower()
    elif message.command and len(message.command) > 1:
        if message.command[1].lower() in ["male", "female"]:
            gender = message.command[1].lower()

    msg = await message.reply_text(f"📥 Downloading document and generating speech (Voice: `{gender}`)...")

    # Download file locally into memory/temp storage
    temp_file_path = await client.download_media(target_doc)
    if not temp_file_path or not os.path.exists(temp_file_path):
        return await msg.edit_text("❌ Failed to download the attached file.")

    # Call ApyHub API
    audio_bytes = await convert_file_to_speech(temp_file_path, gender=gender)

    # Clean up local temporary file immediately
    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)

    if not audio_bytes:
        return await msg.edit_text("❌ Failed to generate speech audio. Check file format size or API key limits.")

    await msg.edit_text("🎵 Speech generated successfully! Uploading audio file...")

    # Save audio stream temporarily to send via Pyrogram
    output_audio_path = "output_speech.mp3"
    with open(output_audio_path, "wb") as f:
        f.write(audio_bytes)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Close", callback_data="tts_close")]
    ])

    try:
        await message.reply_audio(
            audio=output_audio_path,
            caption=f"🎧 **Converted Document to Speech**\n• **Voice:** `{gender}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Error sending audio file: `{e}`", parse_mode=ParseMode.MARKDOWN)
    finally:
        if os.path.exists(output_audio_path):
            os.remove(output_audio_path)


# --- INTERACTIVE CALLBACK ROUTER ---

@app.on_callback_query(filters.regex(r"^tts_close$"))
async def cb_tts_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
