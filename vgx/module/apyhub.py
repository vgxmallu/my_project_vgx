import os
import io
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from vgx import app
from config import Config  # Must contain APY_TOKEN

# ApyHub Markdown to PDF endpoints
BASE_URL = "https://api.eu.apyhub.com/apyhub/convert-markdown-to-pdf"

def get_apy_token() -> str:
    """Retrieves the ApyHub token from config."""
    return getattr(Config.APY_HUB_TOKEN, None)


# --- API CONVERSION HELPERS ---

async def convert_markdown_file_to_pdf(file_path: str, output_name: str = "document.pdf") -> bytes:
    """Uploads a markdown/text file to ApyHub and returns the resulting PDF binary bytes."""
    token = get_apy_token()
    if not token:
        return None

    url = f"{BASE_URL}/md-file-pdf-file"
    params = {"output": output_name}
    headers = {"apy-token": token}

    async with httpx.AsyncClient() as client:
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                resp = await client.post(url, params=params, headers=headers, files=files, timeout=60.0)
                if resp.status_code == 200:
                    return resp.content
                print(f"ApyHub File Error: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"ApyHub File Exception: {e}")
        return None


async def convert_raw_markdown_to_pdf(markdown_text: str, output_name: str = "document.pdf") -> bytes:
    """Sends raw markdown text string to ApyHub and returns the resulting PDF binary bytes."""
    token = get_apy_token()
    if not token:
        return None

    url = f"{BASE_URL}/md-raw-pdf-file"
    params = {"output": output_name}
    headers = {
        "apy-token": token,
        "Content-Type": "text/plain"
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, params=params, headers=headers, content=markdown_text, timeout=30.0)
            if resp.status_code == 200:
                return resp.content
            print(f"ApyHub Raw Text Error: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"ApyHub Raw Text Exception: {e}")
        return None


# --- COMMAND HANDLERS ---

@app.on_message(filters.command(["convertpdf", "pdf"]))
async def cmd_convert_to_pdf(client: Client, message: Message):
    """Command: /convertpdf [text] or reply to a .txt/.md file to generate a PDF."""
    token = get_apy_token()
    if not token:
        return await message.reply_text("❌ Missing `APY_TOKEN` in your `config.py` file. Please configure it to use this feature.")

    target_msg = message.reply_to_message if message.reply_to_message else message
    args = message.command

    status_msg = await message.reply_text("📄 Processing and converting to PDF via ApyHub...")

    pdf_bytes = None
    output_filename = "document.pdf"

    try:
        # Case 1: User replied to a document/file (.md, .txt)
        if target_msg.document or target_msg.text and target_msg != message:
            if target_msg.document:
                file_name = target_msg.document.file_name or "document.md"
                output_filename = f"{os.path.splitext(file_name)[0]}.pdf"
                
                local_path = await client.download_media(target_msg)
                if local_path and os.path.exists(local_path):
                    pdf_bytes = await convert_markdown_file_to_pdf(local_path, output_name=output_filename)
                    if os.path.exists(local_path):
                        os.remove(local_path)
            elif target_msg.text:
                # Fallback if replying to a text message
                raw_text = target_msg.text
                pdf_bytes = await convert_raw_markdown_to_pdf(raw_text, output_name="note.pdf")
                output_filename = "note.pdf"

        # Case 2: User passed raw text in command arguments (e.g., /pdf # Heading\nHello world)
        elif len(args) > 1:
            raw_text = " ".join(args[1:])
            pdf_bytes = await convert_raw_markdown_to_pdf(raw_text, output_name="document.pdf")
            output_filename = "document.pdf"

        else:
            return await status_msg.edit_text(
                "⚠️ **Usage Instructions:**\n\n"
                "• **Option A:** Reply to any `.txt` or `.md` file with `/convertpdf`\n"
                "• **Option B:** Type text directly with the command: `/convertpdf # Title\nYour text here`",
                parse_mode=ParseMode.MARKDOWN
            )

        if not pdf_bytes:
            return await status_msg.edit_text("❌ Failed to generate PDF through ApyHub API. Please check your text format or token limits.")

        await status_msg.edit_text("⬆️ Uploading generated PDF back to Telegram...")

        # Send resulting PDF bytes back to user as a document
        file_io = io.BytesIO(pdf_bytes)
        file_io.name = output_filename

        await message.reply_document(
            document=file_io,
            caption=f"📑 **PDF Successfully Generated!**\n_Powered by ApyHub Markdown to PDF API_",
            parse_mode=ParseMode.MARKDOWN
        )
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ Error during PDF conversion: {str(e)}")


@app.on_message(filters.command("pdfhelp"))
async def cmd_pdf_help(client: Client, message: Message):
    """Command: /pdfhelp - Displays helper guide."""
    help_text = (
        "📖 **ApyHub PDF Bot — Guide**\n\n"
        "• `/convertpdf <markdown text>` — Convert raw markdown text into a PDF.\n"
        "• **Reply to File:** Send or reply to any `.md` or `.txt` file with `/convertpdf`.\n"
        "• `/pdfhelp` — View this instructions guide.\n\n"
        "_Powered by ApyHub Document Intelligence Suite_"
    )
    await message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
