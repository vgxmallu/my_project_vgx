import asyncio
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
from config import Config  # Must contain APY_TOKEN

# --- CONFIGURATION & ENDPOINTS ---
SUBMIT_URL = "https://api.eu.apyhub.com/sharpapi/translate-text"
STATUS_URL = "https://api.eu.apyhub.com/sharpapi/translate-text/job/status"

def get_apy_token() -> str:
    """Retrieves the ApyHub token from config safely."""
    return getattr(Config, "APY_HUB_TOKEN", None)


# --- APYHUB ASYNC TRANSLATION HELPERS ---

async def submit_translation_job(content: str, language: str = None, context: str = None) -> str:
    """Submits a text translation job to ApyHub SharpAPI and returns the job_id."""
    token = get_apy_token()
    if not token:
        return None

    headers = {
        "apy-token": token,
        "Content-Type": "application/json"
    }
    payload = {"content": content.strip()}
    if language:
        payload["language"] = language.strip()
    if context:
        payload["context"] = context.strip()

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(SUBMIT_URL, json=payload, headers=headers, timeout=15.0)
            if resp.status_code in [200, 201]:
                data = resp.json()
                return data.get("job_id")
            print(f"ApyHub Translation Submit Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"ApyHub Translation Submit Exception: {e}")
        return None


async def poll_translation_job(job_id: str, max_retries: int = 30, delay: int = 2) -> dict:
    """Polls the ApyHub translation job status endpoint until completion or failure."""
    token = get_apy_token()
    if not token:
        return {"status": "failed", "error": "Missing token"}

    headers = {"apy-token": token}
    status_endpoint = f"{STATUS_URL}/{job_id}"

    async with httpx.AsyncClient() as client:
        for _ in range(max_retries):
            try:
                resp = await client.get(status_endpoint, headers=headers, timeout=15.0)
                if resp.status_code == 200:
                    res_json = resp.json()
                    data = res_json.get("data", {})
                    attributes = data.get("attributes", {})
                    status = attributes.get("status")

                    if status == "success":
                        return {"status": "success", "result": attributes.get("result", {})}
                    elif status == "failed":
                        return {"status": "failed", "error": attributes.get("error", "Job failed")}
            except Exception as e:
                print(f"Polling Exception: {e}")
            
            await asyncio.sleep(delay)
            
    return {"status": "timeout", "error": "Translation job timed out."}


# --- COMMAND HANDLER ---

@app.on_message(filters.command(["translate", "apytranslate", "sharp-translate"]))
async def cmd_translate(client: Client, message: Message):
    """Command: /translate <text> - Submits an async translation job via ApyHub."""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/translate <text to translate>`\n\n"
            "_Example:_ `/translate Hello, how are you today?`",
            parse_mode=ParseMode.MARKDOWN
        )

    full_text = message.text.partition(" ")[2].strip()
    msg = await message.reply_text("🔄 Enqueuing async translation job via ApyHub SharpAPI...")

    # Submit job
    job_id = await submit_translation_job(content=full_text)
    if not job_id:
        return await msg.edit_text(
            "❌ Failed to submit translation job.\n\n"
            "💡 **Check config:** Ensure `APY_TOKEN` is defined in your `config.py`."
        )

    await msg.edit_text(f"⏳ Job submitted (`{job_id}`). Processing translation in background...")

    # Poll for completion
    job_result = await poll_translation_job(job_id)
    if job_result.get("status") != "success":
        err_msg = job_result.get("error", "Unknown error")
        return await msg.edit_text(f"❌ Translation failed or timed out: `{err_msg}`", parse_mode=ParseMode.MARKDOWN)

    result_data = job_result.get("result", {})
    translated_content = result_data.get("content", "N/A")
    to_lang = result_data.get("to_language", "Auto")
    from_lang = result_data.get("from_language", "Auto")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Close", callback_data="apy_translate_close")]
    ])

    await msg.edit_text(
        f"🌐 **ApyHub Translation Result**\n\n"
        f"• **From:** `{from_lang}` ➔ **To:** `{to_lang}`\n"
        f"• **Original:**\n> {full_text}\n\n"
        f"• **Translated:**\n> {translated_content}",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


# --- INTERACTIVE CALLBACK ROUTER ---

@app.on_callback_query(filters.regex(r"^apy_translate_close$"))
async def cb_apy_translate_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
