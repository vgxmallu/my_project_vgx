import os
import io
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from vgx import app
from config import Config  # Must contain APY_TOKEN

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.enums import ParseMode, ButtonStyle


# ApyHub Markdown to PDF endpoints
BASE_URL = "https://api.eu.apyhub.com/apyhub/convert-markdown-to-pdf"

def get_apy_token() -> str:
    """Retrieves the ApyHub token from config safely."""
    return getattr(Config, "APY_HUB_TOKEN", None)


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



# --- CONFIGURATION & BASE URLS ---
APY_BASE = "https://api.eu.apyhub.com/apyhub"

def get_apy_token() -> str:
    """Retrieves the ApyHub token from config safely."""
    return getattr(Config, "APY_HUB_TOKEN", None)


# --- APYHUB API ASYNC HELPERS ---

async def api_word_to_pdf(file_path: str, output_name: str = "document.pdf") -> bytes:
    """Converts a Word (.docx) document into PDF bytes."""
    token = get_apy_token()
    if not token: return None

    url = f"{APY_BASE}/convert-word-to-pdf/file/download"
    headers = {"apy-token": token}
    params = {"output": output_name}

    async with httpx.AsyncClient() as client:
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                resp = await client.post(url, params=params, headers=headers, files=files, timeout=60.0)
                if resp.status_code == 200:
                    return resp.content
        except Exception as e:
            print(f"Word to PDF Exception: {e}")
        return None


async def api_extract_pdf_text(file_path: str) -> str:
    """Extracts text out of an uploaded PDF file."""
    token = get_apy_token()
    if not token: return None

    url = f"{APY_BASE}/extract-text-from-pdf/file"
    headers = {"apy-token": token}

    async with httpx.AsyncClient() as client:
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                resp = await client.post(url, headers=headers, files=files, timeout=60.0)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("data")
        except Exception as e:
            print(f"Extract PDF Text Exception: {e}")
        return None


async def api_extract_receipt(file_path: str) -> dict:
    """Reads and parses a scanned receipt image or document."""
    token = get_apy_token()
    if not token: return None

    url = f"{APY_BASE}/extract-receipt-data/file"
    headers = {"apy-token": token}
    data = {"requested_service": "apyhub"}

    async with httpx.AsyncClient() as client:
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                resp = await client.post(url, data=data, headers=headers, files=files, timeout=60.0)
                if resp.status_code == 200:
                    return resp.json().get("data", {})
        except Exception as e:
            print(f"Receipt Extraction Exception: {e}")
        return None


async def api_summarize_document(file_path: str, length: str = "medium") -> str:
    """Generates an AI summary of an uploaded PDF or Word document."""
    token = get_apy_token()
    if not token: return None

    url = f"{APY_BASE}/summarize-documents/file"
    headers = {"apy-token": token}
    data = {"summary_length": length}

    async with httpx.AsyncClient() as client:
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                resp = await client.post(url, data=data, headers=headers, files=files, timeout=60.0)
                if resp.status_code == 200:
                    res_json = resp.json()
                    return res_json.get("data", {}).get("summary")
        except Exception as e:
            print(f"Document Summarizer Exception: {e}")
        return None


async def api_markdown_to_pdf(markdown_text: str, output_name: str = "document.pdf") -> bytes:
    """Converts raw Markdown text into PDF bytes."""
    token = get_apy_token()
    if not token: return None

    url = f"{APY_BASE}/convert-markdown-to-pdf/md-raw-pdf-file"
    headers = {"apy-token": token, "Content-Type": "text/plain"}
    params = {"output": output_name}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, params=params, headers=headers, content=markdown_text, timeout=30.0)
            if resp.status_code == 200:
                return resp.content
        except Exception as e:
            print(f"Markdown to PDF Exception: {e}")
        return None


# --- UI KEYBOARD BUILDERS ---

def get_apyhub_suite_menu():
    """Interactive control center for all ApyHub features."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📄 Word ➔ PDF", callback_data="apy_info_word", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("📖 Extract PDF Text", callback_data="apy_info_extract", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("🧾 Scan Receipt", callback_data="apy_info_receipt", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("🤖 Summarize Doc", callback_data="apy_info_sum", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("📝 Markdown ➔ PDF", callback_data="apy_info_md", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("❌ Close", callback_data="apy_close", style=ButtonStyle.DANGER)
        ]
    ])


# --- COMMAND HANDLERS ---

@app.on_message(filters.command(["apyhub", "apyhubsuite"]))
async def cmd_apyhub_hub(client: Client, message: Message):
    """Command: /apyhub - Opens the interactive suite hub."""
    text = (
        "🚀 **ApyHub Document Intelligence Suite**\n\n"
        "Select a tool below or use direct commands:\n\n"
        "• `/wordtopdf` — Reply to a `.docx` file.\n"
        "• `/extractpdf` — Reply to a PDF to pull its text.\n"
        "• `/scanreceipt` — Reply to a receipt image/PDF.\n"
        "• `/summarizedoc` — Reply to a document to summarize it.\n"
        "• `/convertpdf <text>` — Convert markdown text to PDF."
    )
    await message.reply_text(text, reply_markup=get_apyhub_suite_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["wordtopdf", "docpdf"]) & filters.reply)
async def cmd_word_to_pdf(client: Client, message: Message):
    """Command: /wordtopdf (Reply to Word doc)"""
    target = message.reply_to_message
    if not target.document or not target.document.file_name.endswith(('.docx', '.doc', '.odt')):
        return await message.reply_text("⚠️ Please reply to a valid Word document (`.docx`) with `/wordtopdf`.")

    msg = await message.reply_text("📄 Converting Word document to PDF via ApyHub...")
    try:
        path = await client.download_media(target)
        out_name = f"{os.path.splitext(target.document.file_name)[0]}.pdf"
        
        pdf_bytes = await api_word_to_pdf(path, out_name)
        if os.path.exists(path): os.remove(path)

        if not pdf_bytes:
            return await msg.edit_text("❌ Conversion failed. Check your API token or file format.")

        file_io = io.BytesIO(pdf_bytes)
        file_io.name = out_name
        await message.reply_document(document=file_io, caption="📄 **Word Converted to PDF Successfully!**")
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")


@app.on_message(filters.command(["extractpdf", "pdftext"]) & filters.reply)
async def cmd_extract_pdf(client: Client, message: Message):
    """Command: /extractpdf (Reply to PDF)"""
    target = message.reply_to_message
    if not target.document or not target.document.file_name.endswith('.pdf'):
        return await message.reply_text("⚠️ Please reply to a valid PDF document with `/extractpdf`.")

    msg = await message.reply_text("📖 Extracting text out of PDF via ApyHub...")
    try:
        path = await client.download_media(target)
        extracted_text = await api_extract_pdf_text(path)
        if os.path.exists(path): os.remove(path)

        if not extracted_text:
            return await msg.edit_text("❌ Failed to extract text from PDF.")

        # If text is too long for a single message, save as .txt file and send
        if len(extracted_text) > 4000:
            file_io = io.BytesIO(extracted_text.encode("utf-8"))
            file_io.name = "extracted_text.txt"
            await message.reply_document(document=file_io, caption="📖 **Extracted PDF Text File**")
            await msg.delete()
        else:
            await msg.edit_text(f"📖 **Extracted PDF Text:**\n\n{extracted_text}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")


@app.on_message(filters.command(["scanreceipt", "receipt"]) & filters.reply)
async def cmd_scan_receipt(client: Client, message: Message):
    """Command: /scanreceipt (Reply to Receipt Photo or File)"""
    target = message.reply_to_message
    if not target.photo and not target.document:
        return await message.reply_text("⚠️ Please reply to a receipt photo or image/PDF document with `/scanreceipt`.")

    msg = await message.reply_text("🧾 Parsing scanned receipt data via ApyHub...")
    try:
        path = await client.download_media(target)
        receipt_data = await api_extract_receipt(path)
        if os.path.exists(path): os.remove(path)

        if not receipt_data:
            return await msg.edit_text("❌ Could not extract receipt details.")

        formatted_json = json.dumps(receipt_data, indent=2)
        if len(formatted_json) > 3800:
            formatted_json = formatted_json[:3800] + "\n[Truncated...]"

        await msg.edit_text(
            f"🧾 **Scanned Receipt Data Parsed:**\n```json\n{formatted_json}\n```",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")


@app.on_message(filters.command(["summarizedoc", "sumdoc"]) & filters.reply)
async def cmd_summarize_doc(client: Client, message: Message):
    """Command: /summarizedoc (Reply to PDF or Word document)"""
    target = message.reply_to_message
    if not target.document:
        return await message.reply_text("⚠️ Please reply to a PDF or Word document with `/summarizedoc`.")

    msg = await message.reply_text("🤖 Generating AI document summary via ApyHub...")
    try:
        path = await client.download_media(target)
        summary = await api_summarize_document(path, length="medium")
        if os.path.exists(path): os.remove(path)

        if not summary:
            return await msg.edit_text("❌ Failed to generate document summary.")

        await msg.edit_text(
            f"🤖 **Document AI Summary:**\n\n{summary}\n\n_Powered by ApyHub Document Summarizer_",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")


@app.on_message(filters.command(["convertpdf", "pdf"]))
async def cmd_convert_markdown_pdf(client: Client, message: Message):
    """Command: /convertpdf <markdown text>"""
    args = message.command
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:** `/convertpdf # Your Title\nMarkdown content here`")

    raw_text = " ".join(args[1:])
    msg = await message.reply_text("📝 Compiling Markdown into PDF via ApyHub...")

    pdf_bytes = await api_markdown_to_pdf(raw_text, output_name="markdown_document.pdf")
    if not pdf_bytes:
        return await msg.edit_text("❌ Failed to generate PDF from markdown text.")

    file_io = io.BytesIO(pdf_bytes)
    file_io.name = "document.pdf"
    await message.reply_document(document=file_io, caption="📝 **Markdown Converted to PDF Successfully!**")
    await msg.delete()


# --- INTERACTIVE CALLBACK HANDLERS ---

@app.on_callback_query(filters.regex(r"^apy_close$"))
async def cb_apy_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()

@app.on_callback_query(filters.regex(r"^apy_info_(?P<feature>word|extract|receipt|sum|md)$"))
async def cb_apy_info(client: Client, query: CallbackQuery):
    await query.answer()
    f = query.matches[0].group("feature")
    
    guides = {
        "word": "📄 **Word to PDF:**\nReply to any `.docx` file with `/wordtopdf`.",
        "extract": "📖 **Extract PDF Text:**\nReply to any `.pdf` file with `/extractpdf`.",
        "receipt": "🧾 **Scan Receipt:**\nReply to a receipt image or file with `/scanreceipt`.",
        "sum": "🤖 **Summarize Document:**\nReply to a PDF or Word file with `/summarizedoc`.",
        "md": "📝 **Markdown to PDF:**\nType `/convertpdf <your markdown text>` to build a PDF."
    }
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Hub", callback_data="apy_home", style=ButtonStyle.PRIMARY)]])
    await query.message.edit_text(guides.get(f, "N/A"), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^apy_home$"))
async def cb_apy_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🚀 **ApyHub Document Intelligence Suite**\n\n"
        "Select a tool below or use direct commands:"
    )
    await query.message.edit_text(text, reply_markup=get_apyhub_suite_menu(), parse_mode=ParseMode.MARKDOWN)
