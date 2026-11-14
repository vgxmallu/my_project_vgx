import io
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app

# --- CONFIGURATION & ENDPOINT ---
DUMMY_IMAGE_BASE = "https://dummyjson.com/image"


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_dummy_img_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for DummyJSON image generator."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖼️ Square Placeholder", callback_data="dimg_sq"),
            InlineKeyboardButton("📐 Custom Dimensions", callback_data="dimg_help_dims")
        ],
        [
            InlineKeyboardButton("🎨 Colored Badge", callback_data="dimg_badge"),
            InlineKeyboardButton("🔤 Custom Text & Fonts", callback_data="dimg_help_text")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="dimg_close")]
    ])


@app.on_message(filters.command(["dummyimg", "imgmaker", "placeholder"]))
async def cmd_dummyimg_dashboard(client: Client, message: Message):
    """Command: /dummyimg - Opens the DummyJSON dynamic image generator dashboard."""
    text = (
        "🖼️ **DummyJSON Image Generator Suite**\n\n"
        "Generate dynamic placeholder images, custom badges, banners, and typography graphics on the fly "
        "using the interactive controls below:"
    )
    await message.reply_text(text, reply_markup=get_dummy_img_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- GENERATOR COMMAND HANDLER ---
# ==========================================

@app.on_message(filters.command(["genimage", "makeimage"]))
async def cmd_gen_image(client: Client, message: Message):
    """
    Command: /genimage <WIDTHxHEIGHT> [text] [bg_hex] [color_hex]
    Example: /genimage 400x200 Hello+World 282828 ffffff
    """
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/genimage <size> [text] [bg_color] [text_color]`\n\n"
            "_Examples:_\n"
            "• `/genimage 400` (Square 400x400)\n"
            "• `/genimage 600x300 Dashboard+Preview`\n"
            "• `/genimage 500x200 008080 ffffff?text=Custom+Badge`",
            parse_mode=ParseMode.MARKDOWN
        )

    size_spec = args[1].strip()  # e.g., '400' or '500x300'
    extra_params = message.text.partition(args[1])[2].strip().replace(" ", "+")
    
    # Build target URL matching DummyJSON image patterns
    # Format: https://dummyjson.com/image/SIZE/BG/COLOR?params
    target_url = f"{DUMMY_IMAGE_BASE}/{size_spec}"
    if extra_params:
        if not extra_params.startswith("?") and not extra_params.startswith("/"):
            target_url += f"/?text={extra_params}"
        else:
            target_url += extra_params

    msg = await message.reply_text("🎨 Generating placeholder image...")

    async with httpx.AsyncClient(timeout=30.0) as client_http:
        try:
            resp = await client_http.get(target_url)
            if resp.status_code != 200:
                return await msg.edit_text(f"❌ Failed to generate image (HTTP {resp.status_code}). Check your size/color format.")

            image_bytes = io.BytesIO(resp.content)
            image_bytes.name = "dummy_image.png"

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="dimg_home")]
            ])

            await message.reply_photo(
                photo=image_bytes,
                caption=f"✅ **Generated Image URL:**\n`{target_url}`",
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            await msg.delete()
        except Exception as e:
            await msg.edit_text(f"❌ Error generating image: `{e}`", parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^dimg_home$"))
async def cb_dimg_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🖼️ **DummyJSON Image Generator Suite**\n\n"
        "Generate dynamic placeholder images, custom badges, banners, and typography graphics on the fly "
        "using the interactive controls below:"
    )
    await query.message.edit_text(text, reply_markup=get_dummy_img_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^dimg_sq$"))
async def cb_dimg_sq(client: Client, query: CallbackQuery):
    """Sends a quick sample 300x300 square placeholder."""
    await query.answer("Generating sample square image...")
    url = f"{DUMMY_IMAGE_BASE}/300?text=Square+300x300&fontFamily=pacifico"
    
    async with httpx.AsyncClient() as client_http:
        resp = await client_http.get(url)
        if resp.status_code == 200:
            img_io = io.BytesIO(resp.content)
            img_io.name = "square.png"
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="dimg_home")]])
            await query.message.reply_photo(photo=img_io, caption="🖼️ **Sample Square Image (300x300)**", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^dimg_badge$"))
async def cb_dimg_badge(client: Client, query: CallbackQuery):
    """Sends a custom styled colored badge."""
    await query.answer("Generating colored badge...")
    url = f"{DUMMY_IMAGE_BASE}/400x150/008080/ffffff?text=Active+Badge&fontFamily=poppins"

    async with httpx.AsyncClient() as client_http:
        resp = await client_http.get(url)
        if resp.status_code == 200:
            img_io = io.BytesIO(resp.content)
            img_io.name = "badge.png"
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="dimg_home")]])
            await query.message.reply_photo(photo=img_io, caption="🎨 **Custom Styled Badge Example**", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^dimg_help_dims$"))
async def cb_dimg_help_dims(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="dimg_home")]])
    await query.message.edit_text(
        "📐 **Custom Dimensions Guide**\n\n"
        "Generate images specifying width and height parameters:\n\n"
        "• `/genimage 600x300` (Rectangular banner)\n"
        "• `/genimage 250` (Square 250x250)",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^dimg_help_text$"))
async def cb_dimg_help_text(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="dimg_home")]])
    await query.message.edit_text(
        "🔤 **Custom Text, Colors & Fonts**\n\n"
        "DummyJSON supports background hex colors, text hex colors, font families, and formats:\n\n"
        "• **Supported Fonts:** `bitter`, `cairo`, `comfortaa`, `cookie`, `dosis`, `gotham`, `lobster`, `marhey`, `pacifico`, `poppins`, `quicksand`, `qwigley`, `satisfy`, `ubuntu`\n"
        "• **Formats:** `png`, `jpeg`, `webp`\n\n"
        "_Example URL format:_\n"
        "`https://dummyjson.com/image/400x200/282828/ffffff?text=Hello+World&fontFamily=pacifico`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^dimg_close$"))
async def cb_dimg_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
