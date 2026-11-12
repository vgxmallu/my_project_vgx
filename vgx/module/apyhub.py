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




# --- APYHUB API ASYNC HELPERS ---

async def convert_image_file_to_pdf(file_path: str, output_name: str = "document.pdf") -> bytes:
    """Converts an uploaded image (.png, .jpg, etc.) into PDF bytes using ApyHub."""
    token = get_apy_token()
    if not token:
        return None

    url = f"{APY_BASE}/convert-image-to-pdf/file/download"
    headers = {"apy-token": token}
    params = {"output": output_name}

    async with httpx.AsyncClient() as client:
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                resp = await client.post(url, params=params, headers=headers, files=files, timeout=60.0)
                if resp.status_code == 200:
                    return resp.content
                print(f"ApyHub Image to PDF Error: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"ApyHub Image to PDF Exception: {e}")
        return None


async def convert_markdown_url_to_pdf(md_url: str, output_name: str = "document.pdf") -> bytes:
    """Converts a public Markdown URL (e.g., GitHub README) into PDF bytes."""
    token = get_apy_token()
    if not token:
        return None

    url = f"{APY_BASE}/convert-markdown-to-pdf/md-url-pdf-file"
    headers = {"apy-token": token, "Content-Type": "application/json"}
    payload = {"url": md_url}
    params = {"output": output_name}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, params=params, headers=headers, timeout=45.0)
            if resp.status_code == 200:
                return resp.content
        except Exception as e:
            print(f"ApyHub MD URL Exception: {e}")
        return None


async def convert_webpage_to_pdf(web_url: str, output_name: str = "webpage.pdf") -> bytes:
    """Renders a live webpage URL into PDF bytes."""
    token = get_apy_token()
    if not token:
        return None

    url = "https://api.eu.apyhub.com/frolic/convert-webpage-to-pdf-file/url-to-pdf"
    headers = {"apy-token": token}
    data = {"url": web_url, "paper": "A4", "print_background": True}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, data=data, headers=headers, timeout=60.0)
            if resp.status_code == 200:
                return resp.content
        except Exception as e:
            print(f"ApyHub Webpage PDF Exception: {e}")
        return None


async def convert_office_file_to_pdf(file_path: str, output_name: str = "document.pdf") -> bytes:
    """Converts a Word (.docx) document into PDF bytes."""
    token = get_apy_token()
    if not token:
        return None

    url = f"{APY_BASE}/convert-word-to-pdf/word-file-pdf-file"
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
            print(f"ApyHub Office Exception: {e}")
        return None


# --- UI KEYBOARD BUILDERS ---

def get_pdf_suite_menu():
    """Interactive control panel for the ApyHub PDF Suite."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖼 Image ➔ PDF", callback_data="pdf_info_img", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("📝 Markdown ➔ PDF", callback_data="pdf_info_md", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("🔗 Markdown URL ➔ PDF", callback_data="pdf_info_url", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("🌐 Webpage ➔ PDF", callback_data="pdf_info_web", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton("📄 Word Doc ➔ PDF", callback_data="pdf_info_word", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("❌ Close", callback_data="pdf_close", style=ButtonStyle.DANGER)
        ]
    ])


# --- COMMAND HANDLERS ---

@app.on_message(filters.command(["pdfsuite", "pdfhub"]))
async def cmd_pdf_suite_hub(client: Client, message: Message):
    """Command: /pdfsuite - Opens the interactive document conversion hub."""
    text = (
        "📑 **ApyHub Document & PDF Suite**\n\n"
        "Welcome! Choose a conversion tool below or use direct commands:\n\n"
        "• `/imagetopdf` — Reply to any photo/image to convert it to PDF.\n"
        "• `/convertpdf <text>` — Convert markdown text or files.\n"
        "• `/urltopdf <url>` — Convert public Markdown/GitHub URL.\n"
        "• `/webpagepdf <url>` — Snapshot any website into a PDF.\n"
        "• `/wordtopdf` — Reply to a `.docx` file."
    )
    await message.reply_text(text, reply_markup=get_pdf_suite_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["imagetopdf", "imgpdf"]) & filters.reply)
async def cmd_image_to_pdf(client: Client, message: Message):
    """Command: /imagetopdf (Reply to any photo or image document)"""
    target_msg = message.reply_to_message
    
    # Check if replied message contains a photo or image document
    photo = target_msg.photo
    doc = target_msg.document
    
    if not photo and not (doc and doc.mime_type and "image" in doc.mime_type):
        return await message.reply_text("⚠️ Please reply to a valid image (`.png`, `.jpg`, `.jpeg`) with `/imagetopdf`.")

    msg = await message.reply_text("🖼 Downloading image and converting to PDF via ApyHub...")

    try:
        local_path = await client.download_media(target_msg)
        if not local_path or not os.path.exists(local_path):
            return await msg.edit_text("❌ Failed to download image from Telegram.")

        output_name = "converted_image.pdf"
        if doc and doc.file_name:
            output_name = f"{os.path.splitext(doc.file_name)[0]}.pdf"

        pdf_bytes = await convert_image_file_to_pdf(local_path, output_name=output_name)
        
        if os.path.exists(local_path):
            os.remove(local_path)

        if not pdf_bytes:
            return await msg.edit_text("❌ Failed to convert image to PDF via ApyHub.")

        file_io = io.BytesIO(pdf_bytes)
        file_io.name = output_name

        await msg.edit_text("⬆️ Uploading converted PDF...")
        await message.reply_document(
            document=file_io,
            caption="🖼 **Image Converted to PDF Successfully!**\n_Powered by ApyHub Image to PDF API_",
            parse_mode=ParseMode.MARKDOWN
        )
        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"❌ Error during image conversion: {str(e)}")


@app.on_message(filters.command(["urltopdf", "mdurl"]))
async def cmd_url_to_pdf(client: Client, message: Message):
    """Command: /urltopdf <public_markdown_url>"""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/urltopdf <public_url>`\n"
            "_Example:_ `/urltopdf https://raw.githubusercontent.com/user/repo/main/README.md`",
            parse_mode=ParseMode.MARKDOWN
        )

    target_url = args[1].strip()
    msg = await message.reply_text("📥 Fetching Markdown from URL and generating PDF...")

    pdf_bytes = await convert_markdown_url_to_pdf(target_url, output_name="github_document.pdf")
    if not pdf_bytes:
        return await msg.edit_text("❌ Failed to convert Markdown URL to PDF.")

    file_io = io.BytesIO(pdf_bytes)
    file_io.name = "document.pdf"

    await msg.edit_text("⬆️ Uploading generated PDF to Telegram...")
    await message.reply_document(
        document=file_io,
        caption="📑 **Markdown URL Converted Successfully!**\n_Powered by ApyHub Document Intelligence_",
        parse_mode=ParseMode.MARKDOWN
    )
    await msg.delete()


@app.on_message(filters.command(["webpagepdf", "webpdf"]))
async def cmd_webpage_to_pdf(client: Client, message: Message):
    """Command: /webpagepdf <website_url>"""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/webpagepdf <website_url>`\n"
            "_Example:_ `/webpagepdf https://apyhub.com`",
            parse_mode=ParseMode.MARKDOWN
        )

    web_url = args[1].strip()
    msg = await message.reply_text("🌐 Rendering live webpage snapshot into PDF...")

    pdf_bytes = await convert_webpage_to_pdf(web_url, output_name="webpage_snapshot.pdf")
    if not pdf_bytes:
        return await msg.edit_text("❌ Failed to generate webpage snapshot PDF.")

    file_io = io.BytesIO(pdf_bytes)
    file_io.name = "webpage_snapshot.pdf"

    await msg.edit_text("⬆️ Uploading webpage PDF report...")
    await message.reply_document(
        document=file_io,
        caption=f"🌐 **Webpage Snapshot PDF:** `{web_url}`\n_Powered by ApyHub PDF Suite_",
        parse_mode=ParseMode.MARKDOWN
    )
    await msg.delete()


@app.on_message(filters.command(["wordtopdf", "docpdf"]) & filters.reply)
async def cmd_word_to_pdf(client: Client, message: Message):
    """Command: /wordtopdf (Reply to any .docx document)"""
    target_msg = message.reply_to_message
    if not target_msg.document or not target_msg.document.file_name.endswith(('.docx', '.doc')):
        return await message.reply_text("⚠️ Please reply to a valid Word `.docx` file with `/wordtopdf`.")

    msg = await message.reply_text("📥 Downloading Word document & converting...")

    try:
        local_path = await client.download_media(target_msg)
        if not local_path or not os.path.exists(local_path):
            return await msg.edit_text("❌ Failed to download file.")

        orig_name = target_msg.document.file_name
        output_name = f"{os.path.splitext(orig_name)[0]}.pdf"

        pdf_bytes = await convert_office_file_to_pdf(local_path, output_name=output_name)
        
        if os.path.exists(local_path):
            os.remove(local_path)

        if not pdf_bytes:
            return await msg.edit_text("❌ Failed to convert Word document to PDF.")

        file_io = io.BytesIO(pdf_bytes)
        file_io.name = output_name

        await msg.edit_text("⬆️ Uploading converted PDF...")
        await message.reply_document(
            document=file_io,
            caption=f"📄 **Word Document Converted:** `{output_name}`\n_Powered by ApyHub_",
            parse_mode=ParseMode.MARKDOWN
        )
        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"❌ Error during conversion: {str(e)}")


# --- INTERACTIVE CALLBACK ROUTERS ---

@app.on_callback_query(filters.regex(r"^pdf_close$"))
async def cb_pdf_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()

@app.on_callback_query(filters.regex(r"^pdf_info_(?P<type>img|md|url|web|word)$"))
async def cb_pdf_info(client: Client, query: CallbackQuery):
    await query.answer()
    t = query.matches[0].group("type")
    
    guides = {
        "img": "🖼 **Image to PDF:**\nReply to any photo or image file with `/imagetopdf`.",
        "md": "📝 **Markdown Text to PDF:**\nSend raw text or files using `/convertpdf`.",
        "url": "🔗 **Markdown URL to PDF:**\nPass any public Markdown link using `/urltopdf <url>`.",
        "web": "🌐 **Webpage Snapshot to PDF:**\nCapture any live website using `/webpagepdf <url>`.",
        "word": "📄 **Word Document to PDF:**\nReply to any `.docx` file with `/wordtopdf`."
    }
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="pdf_home", style=ButtonStyle.PRIMARY)]])
    await query.message.edit_text(guides.get(t, "N/A"), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^pdf_home$"))
async def cb_pdf_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "📑 **ApyHub Document & PDF Suite**\n\n"
        "Welcome! Choose a conversion tool below or use direct commands:"
    )
    await query.message.edit_text(text, reply_markup=get_pdf_suite_menu(), parse_mode=ParseMode.MARKDOWN)
