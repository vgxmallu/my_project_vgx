import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
import random
from datetime import datetime, timedelta

# --- CONFIGURATION & ENDPOINT ---
# Uses a reliable public mock REST wrapper or placeholder generator for Faker data
FAKER_API_BASE = "https://fakerapi.it/api/v1"


async def fetch_fake_data(resource: str, quantity: int = 1) -> dict:
    """Async helper to fetch mock data from Faker API wrapper."""
    url = f"{FAKER_API_BASE}/{resource}?_quantity={quantity}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.json()
            print(f"Faker API Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"Faker API Exception: {e}")
        return {}


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_faker_main_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for Faker data generator."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Fake User Persona", callback_data="faker_user"),
            InlineKeyboardButton("📍 Fake Address", callback_data="faker_address")
        ],
        [
            InlineKeyboardButton("🏢 Fake Company", callback_data="faker_company"),
            InlineKeyboardButton("💳 Fake Credit Card", callback_data="faker_card")
        ],
        [
            InlineKeyboardButton("📚 Read Documentation", url="https://fakerjs.dev/api/"),
            InlineKeyboardButton("❌ Close", callback_data="faker_close")
        ]
    ])


@app.on_message(filters.command(["faker", "mock", "fakegen"]))
async def cmd_faker_dashboard(client: Client, message: Message):
    """Command: /faker - Opens the interactive Faker mock data generation dashboard."""
    text = (
        "🎭 **Faker Mock Data Intelligence Suite**\n\n"
        "Generate realistic fake user profiles, addresses, company info, and financial test records instantly "
        "using the interactive controls below:"
    )
    await message.reply_text(text, reply_markup=get_faker_main_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.command(["fakeuser", "fakeperson"]))
async def cmd_fake_user(client: Client, message: Message):
    """Command: /fakeuser - Generates realistic random user profiles."""
    msg = await message.reply_text("👤 Generating fake user profile...")
    data = await fetch_fake_data("persons", quantity=1)
    data_list = data.get("data", [])

    if not data_list:
        return await msg.edit_text("❌ Failed to generate user persona.")

    user = data_list[0]
    fname = user.get("firstname", "")
    lname = user.get("lastname", "")
    email = user.get("email", "")
    gender = user.get("gender", "")
    phone = user.get("phone", "")
    dob = user.get("birthday", "")
    address = user.get("address", {})
    street = address.get("street", "")
    city = address.get("city", "")
    country = address.get("country", "")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="faker_user")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="faker_home")]
    ])

    await msg.edit_text(
        f"👤 **Generated User Persona**\n\n"
        f"• **Name:** `{fname} {lname}`\n"
        f"• **Gender:** `{gender}` | **DOB:** `{dob}`\n"
        f"• **Email:** `{email}`\n"
        f"• **Phone:** `{phone}`\n"
        f"• **Location:** `{street}, {city}, {country}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_message(filters.command(["fakeaddress"]))
async def cmd_fake_address(client: Client, message: Message):
    """Command: /fakeaddress - Generates fake geographical address details."""
    msg = await message.reply_text("📍 Generating mock address...")
    data = await fetch_fake_data("addresses", quantity=1)
    data_list = data.get("data", [])

    if not data_list:
        return await msg.edit_text("❌ Failed to generate address.")

    addr = data_list[0]
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="faker_address")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="faker_home")]
    ])

    await msg.edit_text(
        f"📍 **Generated Mock Address**\n\n"
        f"• **Street:** `{addr.get('street', '')}`\n"
        f"• **Street Name:** `{addr.get('streetName', '')}`\n"
        f"• **City:** `{addr.get('city', '')}`\n"
        f"• **State:** `{addr.get('state', '')}`\n"
        f"• **Zipcode:** `{addr.get('zipcode', '')}`\n"
        f"• **Country:** `{addr.get('country', '')}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^faker_home$"))
async def cb_faker_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🎭 **Faker Mock Data Intelligence Suite**\n\n"
        "Generate realistic fake user profiles, addresses, company info, and financial test records instantly "
        "using the interactive controls below:"
    )
    await query.message.edit_text(text, reply_markup=get_faker_main_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^faker_user$"))
async def cb_faker_user(client: Client, query: CallbackQuery):
    await query.answer("Generating user...")
    data = await fetch_fake_data("persons", quantity=1)
    data_list = data.get("data", [])

    if not data_list:
        return await query.answer("Failed to generate user.", show_alert=True)

    user = data_list[0]
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="faker_user")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="faker_home")]
    ])

    await query.message.edit_text(
        f"👤 **Generated User Persona**\n\n"
        f"• **Name:** `{user.get('firstname')} {user.get('lastname')}`\n"
        f"• **Email:** `{user.get('email')}`\n"
        f"• **Phone:** `{user.get('phone')}`\n"
        f"• **Country:** `{user.get('address', {}).get('country')}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^faker_address$"))
async def cb_faker_address(client: Client, query: CallbackQuery):
    await query.answer("Generating address...")
    data = await fetch_fake_data("addresses", quantity=1)
    data_list = data.get("data", [])

    if not data_list:
        return await query.answer("Failed to generate address.", show_alert=True)

    addr = data_list[0]
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="faker_address")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="faker_home")]
    ])

    await query.message.edit_text(
        f"📍 **Generated Mock Address**\n\n"
        f"• **Street:** `{addr.get('street')}`\n"
        f"• **City:** `{addr.get('city')}`\n"
        f"• **Zipcode:** `{addr.get('zipcode')}`\n"
        f"• **Country:** `{addr.get('country')}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^faker_company$"))
async def cb_faker_company(client: Client, query: CallbackQuery):
    await query.answer("Generating company...")
    data = await fetch_fake_data("companies", quantity=1)
    data_list = data.get("data", [])

    if not data_list:
        return await query.answer("Failed to generate company.", show_alert=True)

    comp = data_list[0]
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="faker_company")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="faker_home")]
    ])

    await query.message.edit_text(
        f"🏢 **Generated Mock Company**\n\n"
        f"• **Company Name:** `{comp.get('name')}`\n"
        f"• **Catch Phrase:** _{comp.get('catchPhrase', 'N/A')}_\n"
        f"• **Email:** `{comp.get('email')}`\n"
        f"• **Website:** `{comp.get('website')}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^faker_card$"))
async def cb_faker_card(client: Client, query: CallbackQuery):
    await query.answer("Generating credit card...")
    data = await fetch_fake_data("credit_cards", quantity=1)
    data_list = data.get("data", [])

    if not data_list:
        return await query.answer("Failed to generate card.", show_alert=True)

    card = data_list[0]
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="faker_card")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="faker_home")]
    ])

    await query.message.edit_text(
        f"💳 **Generated Mock Credit Card**\n\n"
        f"• **Type:** `{card.get('type')}`\n"
        f"• **Number:** `{card.get('number')}`\n"
        f"• **Expiration:** `{card.get('expiration')}`\n"
        f"• **Owner:** `{card.get('owner')}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^faker_close$"))
async def cb_faker_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()


# --- CONFIGURATION & STATE ---
# Mock API wrapper for structured random test records
FAKER_API_BASE = "https://fakerapi.ai/api/v1" if False else "https://fakerapi.it/api/v1"

# Persistent active seed state for reproducible random generation
CURRENT_SEED = None


def set_custom_seed(seed_value: int):
    """Sets Python's random seed to simulate Faker's reproducible seed behavior."""
    global CURRENT_SEED
    CURRENT_SEED = seed_value
    random.seed(seed_value)


async def fetch_random_record(resource: str) -> dict:
    """Fetches a random mock data entity."""
    url = f"{FAKER_API_BASE}/{resource}?_quantity=1"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                if data:
                    return data[0]
        except Exception as e:
            print(f"Faker Randomizer Exception: {e}")
        return {}


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_randomizer_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for Faker Randomizer controls."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 Generate Float (0-1)", callback_data="rand_float"),
            InlineKeyboardButton("🔢 Roll Random Int", callback_data="rand_int")
        ],
        [
            InlineKeyboardButton("🌱 Set Seed (42)", callback_data="rand_seed_42"),
            InlineKeyboardButton("🧹 Clear Seed", callback_data="rand_seed_clear")
        ],
        [
            InlineKeyboardButton("👤 Random Seeded Profile", callback_data="rand_profile"),
            InlineKeyboardButton("📚 API Docs", url="https://fakerjs.dev/api/randomizer")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="rand_close")]
    ])


@app.on_message(filters.command(["randomizer", "fakerand", "seed"]))
async def cmd_randomizer_dashboard(client: Client, message: Message):
    """Command: /randomizer - Opens the interactive Faker Randomizer dashboard."""
    seed_status = f"`{CURRENT_SEED}`" if CURRENT_SEED is not None else "_None (Unseeded)_"
    text = (
        "🎲 **Faker Randomizer & Seed Intelligence Suite**\n\n"
        f"• **Current Active Seed:** {seed_status}\n\n"
        "Control pseudo-random generation, test reproducible seeds, and generate random datasets using the UI below:"
    )
    await message.reply_text(text, reply_markup=get_randomizer_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.command(["setseed"]))
async def cmd_set_seed(client: Client, message: Message):
    """Command: /setseed <number> - Sets a custom random seed for reproducibility."""
    args = message.command
    if len(args) < 2 or not args[1].isdigit():
        return await message.reply_text(
            "⚠️ **Usage:** `/setseed <number>`\n\n_Example:_ `/setseed 42`",
            parse_mode=ParseMode.MARKDOWN
        )

    seed_val = int(args[1])
    set_custom_seed(seed_val)

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="rand_home")]])
    await message.reply_text(
        f"🌱 **Seed Successfully Updated!**\n\n"
        f"• **New Seed:** `{seed_val}`\n"
        f"• Subsequent random generations will now be 100% reproducible.",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^rand_home$"))
async def cb_rand_home(client: Client, query: CallbackQuery):
    await query.answer()
    seed_status = f"`{CURRENT_SEED}`" if CURRENT_SEED is not None else "_None (Unseeded)_"
    text = (
        "🎲 **Faker Randomizer & Seed Intelligence Suite**\n\n"
        f"• **Current Active Seed:** {seed_status}\n\n"
        "Control pseudo-random generation, test reproducible seeds, and generate random datasets using the UI below:"
    )
    await query.message.edit_text(text, reply_markup=get_randomizer_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^rand_float$"))
async def cb_rand_float(client: Client, query: CallbackQuery):
    val = random.random()
    await query.answer(f"Generated: {val:.4f}", show_alert=True)


@app.on_callback_query(filters.regex(r"^rand_int$"))
async def cb_rand_int(client: Client, query: CallbackQuery):
    val = random.randint(1, 1000)
    await query.answer(f"Random Integer: {val}", show_alert=True)


@app.on_callback_query(filters.regex(r"^rand_seed_42$"))
async def cb_rand_seed_42(client: Client, query: CallbackQuery):
    set_custom_seed(42)
    await query.answer("Seed set to 42 🌿", show_alert=False)
    
    seed_status = f"`{CURRENT_SEED}`"
    text = (
        "🎲 **Faker Randomizer & Seed Intelligence Suite**\n\n"
        f"• **Current Active Seed:** {seed_status}\n\n"
        "Seed locked to `42`. All outputs will now be deterministic."
    )
    await query.message.edit_text(text, reply_markup=get_randomizer_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^rand_seed_clear$"))
async def cb_rand_seed_clear(client: Client, query: CallbackQuery):
    global CURRENT_SEED
    CURRENT_SEED = None
    random.seed()  # Reset to system entropy source
    await query.answer("Seed cleared 🧹", show_alert=False)
    
    text = (
        "🎲 **Faker Randomizer & Seed Intelligence Suite**\n\n"
        f"• **Current Active Seed:** _None (System Entropy)_\n\n"
        "Randomizer reset to standard non-deterministic behavior."
    )
    await query.message.edit_text(text, reply_markup=get_randomizer_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^rand_profile$"))
async def cb_rand_profile(client: Client, query: CallbackQuery):
    await query.answer("Fetching seeded profile...")
    user = await fetch_random_record("persons")
    
    if not user:
        return await query.answer("Failed to generate entity.", show_alert=True)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="rand_profile")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="rand_home")]
    ])

    await query.message.edit_text(
        f"👤 **Seeded Random User Persona**\n\n"
        f"• **Name:** `{user.get('firstname')} {user.get('lastname')}`\n"
        f"• **Email:** `{user.get('email')}`\n"
        f"• **Active Seed:** `{CURRENT_SEED if CURRENT_SEED is not None else 'Unseeded'}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_callback_query(filters.regex(r"^rand_close$"))
async def cb_rand_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()


# --- MOCK DATA POOLS (Faker Airline Standard) ---
AIRLINES = [
    {"name": "Singapore Airlines", "iata": "SQ"},
    {"name": "Emirates", "iata": "EK"},
    {"name": "Delta Air Lines", "iata": "DL"},
    {"name": "Lufthansa", "iata": "LH"},
    {"name": "Qatar Airways", "iata": "QR"},
    {"name": "Japan Airlines", "iata": "JL"}
]

AIRPORTS = [
    {"city": "New York (JFK)", "code": "JFK"},
    {"city": "London (LHR)", "code": "LHR"},
    {"city": "Tokyo (HND)", "code": "HND"},
    {"city": "Dubai (DXB)", "code": "DXB"},
    {"city": "Singapore (SIN)", "code": "SIN"},
    {"city": "Paris (CDG)", "code": "CDG"},
    {"city": "Sydney (SYD)", "code": "SYD"}
]

AIRCRAFT_TYPES = [
    {"name": "Airbus A350-900", "type": "Widebody"},
    {"name": "Boeing 777-300ER", "type": "Widebody"},
    {"name": "Airbus A321neo", "type": "Narrowbody"},
    {"name": "Boeing 787-9 Dreamliner", "type": "Widebody"}
]

FIRST_NAMES = ["Alexander", "Sophia", "Liam", "Emma", "Noah", "Olivia", "Lucas", "Ava"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]


def generate_flight_itinerary() -> dict:
    """Simulates Faker.js airline & booking generators for complete itineraries."""
    airline = random.choice(AIRLINES)
    origin, destination = random.sample(AIRPORTS, 2)
    aircraft = random.choice(AIRCRAFT_TYPES)
    
    # Flight number (e.g., EK402)
    flight_num = f"{airline['iata']}{random.randint(100, 999)}"
    
    # Seat (e.g., 14A, 32K)
    row = random.randint(5, 45)
    seat_letter = random.choice(["A", "B", "C", "D", "E", "F", "J", "K"])
    seat = f"{row}{seat_letter}"
    
    # Record Locator / PNR (6 alphanumeric characters)
    pnr = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=6))
    
    # Passenger
    passenger = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    
    # Timings
    dep_time = datetime.utcnow() + timedelta(hours=random.randint(6, 72))
    arr_time = dep_time + timedelta(hours=random.randint(3, 14), minutes=random.choice([0, 15, 30, 45]))

    return {
        "passenger": passenger,
        "airline": airline["name"],
        "flight": flight_num,
        "origin": origin["city"],
        "destination": destination["city"],
        "aircraft": aircraft["name"],
        "seat": seat,
        "pnr": pnr,
        "departure": dep_time.strftime("%d %b %Y, %H:%M UTC"),
        "arrival": arr_time.strftime("%d %b %Y, %H:%M UTC"),
        "class": random.choice(["Economy", "Business Class", "First Class"])
    }


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_airline_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for flight generator controls."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✈️ Generate Itinerary", callback_data="air_generate"),
            InlineKeyboardButton("💺 Shuffle Seat", callback_data="air_generate")
        ],
        [
            InlineKeyboardButton("📚 Airline Docs", url="https://fakerjs.dev/api/airline.html"),
            InlineKeyboardButton("❌ Close", callback_data="air_close")
        ]
    ])


@app.on_message(filters.command(["airline", "flight", "boardingpass"]))
async def cmd_airline_dashboard(client: Client, message: Message):
    """Command: /airline - Opens the interactive Faker Airline Itinerary generator."""
    text = (
        "✈️ **Faker Airline Intelligence Suite**\n\n"
        "Generate realistic airline bookings, boarding passes, flight numbers, and PNR locators instantly "
        "using the interactive controls below:"
    )
    await message.reply_text(text, reply_markup=get_airline_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.command(["bookflight", "itinerary"]))
async def cmd_generate_itinerary(client: Client, message: Message):
    """Command: /bookflight - Generates a complete mock boarding pass itinerary."""
    flight = generate_flight_itinerary()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="air_generate")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="air_home")]
    ])

    itinerary_text = (
        f"🎫 **CONFIRMED FLIGHT ITINERARY**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Passenger Name:** `{flight['passenger']}`\n"
        f"• **Booking Reference (PNR):** `{flight['pnr']}`\n\n"
        f"✈️ **Flight Details:**\n"
        f"• **Airline:** `{flight['airline']}` (`{flight['flight']}`)\n"
        f"• **Aircraft:** `{flight['aircraft']}`\n"
        f"• **Travel Class:** `{flight['class']}`\n"
        f"• **Seat Assignment:** `{flight['seat']}`\n\n"
        f"📍 **Route & Schedule:**\n"
        f"• **From:** `{flight['origin']}`\n"
        f"• **Departure:** `{flight['departure']}`\n"
        f"• **To:** `{flight['destination']}`\n"
        f"• **Arrival:** `{flight['arrival']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await message.reply_text(itinerary_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^air_home$"))
async def cb_air_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "✈️ **Faker Airline Intelligence Suite**\n\n"
        "Generate realistic airline bookings, boarding passes, flight numbers, and PNR locators instantly "
        "using the interactive controls below:"
    )
    await query.message.edit_text(text, reply_markup=get_airline_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^air_generate$"))
async def cb_air_generate(client: Client, query: CallbackQuery):
    await query.answer("Generating new flight itinerary...")
    flight = generate_flight_itinerary()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="air_generate")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="air_home")]
    ])

    itinerary_text = (
        f"🎫 **CONFIRMED FLIGHT ITINERARY**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Passenger Name:** `{flight['passenger']}`\n"
        f"• **Booking Reference (PNR):** `{flight['pnr']}`\n\n"
        f"✈️ **Flight Details:**\n"
        f"• **Airline:** `{flight['airline']}` (`{flight['flight']}`)\n"
        f"• **Aircraft:** `{flight['aircraft']}`\n"
        f"• **Travel Class:** `{flight['class']}`\n"
        f"• **Seat Assignment:** `{flight['seat']}`\n\n"
        f"📍 **Route & Schedule:**\n"
        f"• **From:** `{flight['origin']}`\n"
        f"• **Departure:** `{flight['departure']}`\n"
        f"• **To:** `{flight['destination']}`\n"
        f"• **Arrival:** `{flight['arrival']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await query.message.edit_text(itinerary_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^air_close$"))
async def cb_air_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()


# --- MOCK DATA POOLS (Faker.js Animal Standards) ---
ANIMAL_DATABASE = {
    "dog": [
        {"species": "Golden Retriever", "type": "Dog", "sound": "Woof!", "trait": "Friendly & Intelligent"},
        {"species": "German Shepherd", "type": "Dog", "sound": "Bark!", "trait": "Loyal & Courageous"},
        {"species": "French Bulldog", "type": "Dog", "sound": "Snort!", "trait": "Playful & Adaptable"},
        {"species": "Siberian Husky", "type": "Dog", "sound": "Howl!", "trait": "Energetic & Outgoing"}
    ],
    "cat": [
        {"species": "Maine Coon", "type": "Cat", "sound": "Meow!", "trait": "Gentle Giant & Friendly"},
        {"species": "Siamese", "type": "Cat", "sound": "Purr!", "trait": "Vocal & Social"},
        {"species": "British Shorthair", "type": "Cat", "sound": "Meow!", "trait": "Calm & Dignified"},
        {"species": "Ragdoll", "type": "Cat", "sound": "Purr!", "trait": "Affectionate & Docile"}
    ],
    "bear": [
        {"species": "Grizzly Bear", "type": "Bear", "sound": "Roar!", "trait": "Solitary & Powerful"},
        {"species": "Polar Bear", "type": "Bear", "sound": "Growl!", "trait": "Expert Swimmer & Resilient"},
        {"species": "Panda Bear", "type": "Bear", "sound": "Huff!", "trait": "Herbivorous & Gentle"}
    ],
    "bird": [
        {"species": "Bald Eagle", "type": "Bird", "sound": "Screech!", "trait": "Majestic & Keen Vision"},
        {"species": "Peregrine Falcon", "type": "Bird", "sound": "Kek-kek!", "trait": "Incredible Diving Speed"},
        {"species": "Emperor Penguin", "type": "Bird", "sound": "Honk!", "trait": "Social & Cold-Resistant"}
    ],
    "insect": [
        {"species": "Monarch Butterfly", "type": "Insect", "sound": "Silent", "trait": "Famous Long-Distance Migrator"},
        {"species": "Honey Bee", "type": "Insect", "sound": "Buzz!", "trait": "Industrious Pollinator"},
        {"species": "Green Darner Dragonfly", "type": "Insect", "sound": "Whirr!", "trait": "Exceptional Aerial Predator"}
    ]
}

PET_NAMES = ["Bella", "Charlie", "Luna", "Milo", "Oliver", "Lucy", "Leo", "Bailey", "Zoe", "Max"]


def generate_random_animal(category: str = None) -> dict:
    """Simulates Faker.js animal generators (type, species, and pet names)."""
    if category and category in ANIMAL_DATABASE:
        cat_key = category
    else:
        cat_key = random.choice(list(ANIMAL_DATABASE.keys()))

    entity = random.choice(ANIMAL_DATABASE[cat_key])
    pet_name = random.choice(PET_NAMES)
    age = random.randint(1, 12)

    return {
        "category": cat_key.capitalize(),
        "species": entity["species"],
        "type": entity["type"],
        "sound": entity["sound"],
        "trait": entity["trait"],
        "pet_name": pet_name,
        "age": f"{age} {'year' if age == 1 else 'years'} old"
    }


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_animal_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for Faker Animal controls."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🐾 Random Animal", callback_data="ani_random"),
            InlineKeyboardButton("🐶 Dogs", callback_data="ani_dog")
        ],
        [
            InlineKeyboardButton("🐱 Cats", callback_data="ani_cat"),
            InlineKeyboardButton("🦅 Birds", callback_data="ani_bird")
        ],
        [
            InlineKeyboardButton("📚 Faker.js Docs", url="https://fakerjs.dev/api/animal.html"),
            InlineKeyboardButton("❌ Close", callback_data="ani_close")
        ]
    ])


@app.on_message(filters.command(["animal", "fakeranimal", "pets"]))
async def cmd_animal_dashboard(client: Client, message: Message):
    """Command: /animal - Opens the interactive Faker Animal generator dashboard."""
    text = (
        "🐾 **Faker Animal Intelligence Suite**\n\n"
        "Generate random animal species, pet names, wildlife classifications, and biological traits "
        "using the interactive controls below:"
    )
    await message.reply_text(text, reply_markup=get_animal_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.command(["fakeanimal", "randomanimal"]))
async def cmd_generate_animal(client: Client, message: Message):
    """Command: /fakeanimal [category] - Generates a mock animal profile."""
    args = message.command
    cat_arg = args[1].lower().strip() if len(args) > 1 else None

    animal = generate_random_animal(cat_arg)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="ani_random")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="ani_home")]
    ])

    response_text = (
        f"🐾 **FAKER ANIMAL PROFILE**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Category:** `{animal['category']}`\n"
        f"• **Species:** `{animal['species']}`\n"
        f"• **Typical Sound:** `{animal['sound']}`\n"
        f"• **Key Trait:** _{animal['trait']}_\n\n"
        f"🏷️ **Mock Pet Persona (Bonus):**\n"
        f"• **Suggested Name:** `{animal['pet_name']}`\n"
        f"• **Estimated Age:** `{animal['age']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await message.reply_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^ani_home$"))
async def cb_ani_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🐾 **Faker Animal Intelligence Suite**\n\n"
        "Generate random animal species, pet names, wildlife classifications, and biological traits "
        "using the interactive controls below:"
    )
    await query.message.edit_text(text, reply_markup=get_animal_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^ani_(?Pcat>random|dog|cat|bird)$"))
async def cb_ani_filter(client: Client, query: CallbackQuery):
    match_val = query.matches[0].group("cat")
    category = None if match_val == "random" else match_val

    await query.answer(f"Generating {match_val} profile...")
    animal = generate_random_animal(category)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data=f"ani_{match_val}")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="ani_home")]
    ])

    response_text = (
        f"🐾 **FAKER ANIMAL PROFILE**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Category:** `{animal['category']}`\n"
        f"• **Species:** `{animal['species']}`\n"
        f"• **Typical Sound:** `{animal['sound']}`\n"
        f"• **Key Trait:** _{animal['trait']}_\n\n"
        f"🏷️ **Mock Pet Persona:**\n"
        f"• **Suggested Name:** `{animal['pet_name']}`\n"
        f"• **Estimated Age:** `{animal['age']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await query.message.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^ani_close$"))
async def cb_ani_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()



# --- MOCK DATA POOLS (Faker.js Book Module Standards) ---
BOOK_TITLES = [
    "The Shadow of the Wind", "Echoes of Eternity", "Silent Echoes", 
    "Beyond the Horizon", "The Clockwork Empire", "Chronicles of the Valiant", 
    "Realm of Glass", "Whispers in the Dark", "The Last Alchemist", "Summit of Dreams"
]

AUTHORS = [
    "J.R. Vance", "Elena Rostova", "Marcus Sterling", "Aria Montgomery", 
    "Julian Cross", "Beatrice Thorne", "Liam Vance", "Nora Sterling"
]

GENRES = [
    "Science Fiction", "Epic Fantasy", "Mystery & Thriller", 
    "Historical Fiction", "Cyberpunk", "Dystopian", "Romance", "Biographical"
]

SERIES = [
    "The Chronos Chronicles", "Aria of Elements", "The Obsidian Trilogy", 
    "Legacy of Empires", "Shadow Guild Series", "Starlight Saga"
]

PUBLISHERS = [
    "Penguin Random House", "HarperCollins", "Macmillan Publishers", 
    "Simon & Schuster", "Addison-Wesley", "O'Reilly Media"
]

FORMATS = ["Hardcover", "Paperback", "E-Book", "Audiobook"]


def generate_book_record() -> dict:
    """Simulates Faker.js book generators (title, author, genre, series, publisher, format)."""
    return {
        "title": random.choice(BOOK_TITLES),
        "author": random.choice(AUTHORS),
        "genre": random.choice(GENRES),
        "series": random.choice(SERIES),
        "publisher": random.choice(PUBLISHERS),
        "format": random.choice(FORMATS),
        "isbn": f"978-{random.randint(0, 9)}-{random.randint(100, 999)}-{random.randint(10000, 99999)}-{random.randint(0, 9)}"
    }


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_book_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for Faker Book controls."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📚 Random Book Entry", callback_data="book_random"),
            InlineKeyboardButton("📖 Epic Fantasy", callback_data="book_fantasy")
        ],
        [
            InlineKeyboardButton("🎧 Audiobook Format", callback_data="book_audio"),
            InlineKeyboardButton("📚 Book Docs", url="https://fakerjs.dev/api/book.html")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="book_close")]
    ])


@app.on_message(filters.command(["book", "fakerbook", "library"]))
async def cmd_book_dashboard(client: Client, message: Message):
    """Command: /book - Opens the interactive Faker Book generator dashboard."""
    text = (
        "📚 **Faker Book Intelligence Suite**\n\n"
        "Generate random book titles, authors, publishers, genres, ISBN identifiers, and catalog entries "
        "using the interactive controls below:"
    )
    await message.reply_text(text, reply_markup=get_book_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.command(["fakebook", "randombook"]))
async def cmd_generate_book(client: Client, message: Message):
    """Command: /fakebook - Generates a complete mock book catalog record."""
    book = generate_book_record()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="book_random")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="book_home")]
    ])

    response_text = (
        f"📚 **FAKER BOOK CATALOG RECORD**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Title:** `{book['title']}`\n"
        f"• **Author:** `{book['author']}`\n"
        f"• **Genre:** `{book['genre']}`\n"
        f"• **Series:** _{book['series']}_\n"
        f"• **Publisher:** `{book['publisher']}`\n"
        f"• **Format:** `{book['format']}`\n"
        f"• **ISBN:** `{book['isbn']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await message.reply_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^book_home$"))
async def cb_book_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "📚 **Faker Book Intelligence Suite**\n\n"
        "Generate random book titles, authors, publishers, genres, ISBN identifiers, and catalog entries "
        "using the interactive controls below:"
    )
    await query.message.edit_text(text, reply_markup=get_book_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^book_random$"))
async def cb_book_random(client: Client, query: CallbackQuery):
    await query.answer("Generating book record...")
    book = generate_book_record()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="book_random")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="book_home")]
    ])

    response_text = (
        f"📚 **FAKER BOOK CATALOG RECORD**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Title:** `{book['title']}`\n"
        f"• **Author:** `{book['author']}`\n"
        f"• **Genre:** `{book['genre']}`\n"
        f"• **Series:** _{book['series']}_\n"
        f"• **Publisher:** `{book['publisher']}`\n"
        f"• **Format:** `{book['format']}`\n"
        f"• **ISBN:** `{book['isbn']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await query.message.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^book_fantasy$"))
async def cb_book_fantasy(client: Client, query: CallbackQuery):
    await query.answer("Filtering fantasy genre...")
    book = generate_book_record()
    book["genre"] = "Epic Fantasy"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="book_random")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="book_home")]
    ])

    response_text = (
        f"📚 **FAKER BOOK CATALOG RECORD**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Title:** `{book['title']}`\n"
        f"• **Author:** `{book['author']}`\n"
        f"• **Genre:** `Epic Fantasy`\n"
        f"• **Series:** _{book['series']}_\n"
        f"• **Publisher:** `{book['publisher']}`\n"
        f"• **Format:** `{book['format']}`\n"
        f"• **ISBN:** `{book['isbn']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await query.message.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^book_audio$"))
async def cb_book_audio(client: Client, query: CallbackQuery):
    await query.answer("Selecting audiobook format...")
    book = generate_book_record()
    book["format"] = "Audiobook"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="book_random")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="book_home")]
    ])

    response_text = (
        f"📚 **FAKER BOOK CATALOG RECORD**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Title:** `{book['title']}`\n"
        f"• **Author:** `{book['author']}`\n"
        f"• **Genre:** `{book['genre']}`\n"
        f"• **Series:** _{book['series']}_\n"
        f"• **Publisher:** `{book['publisher']}`\n"
        f"• **Format:** `Audiobook`\n"
        f"• **ISBN:** `{book['isbn']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await query.message.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^book_close$"))
async def cb_book_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()


# --- MOCK DATA POOLS (Faker.js Color Module Standards) ---
COLOR_DATABASE = [
    {"name": "Crimson", "hex": "#DC143C", "rgb": "220, 20, 60", "hsl": "348, 83%, 47%"},
    {"name": "Electric Indigo", "hex": "#6F00FF", "rgb": "111, 0, 255", "hsl": "266, 100%, 50%"},
    {"name": "Emerald Green", "hex": "#50C878", "rgb": "80, 200, 120", "hsl": "140, 55%, 55%"},
    {"name": "Neon Cyan", "hex": "#00FFFF", "rgb": "0, 255, 255", "hsl": "180, 100%, 50%"},
    {"name": "Sunset Orange", "hex": "#FD5E53", "rgb": "253, 94, 83", "hsl": "4, 97%, 66%"},
    {"name": "Royal Purple", "hex": "#7851A9", "rgb": "120, 81, 169", "hsl": "267, 35%, 49%"},
    {"name": "Golden Yellow", "hex": "#FFDF00", "rgb": "255, 223, 0", "hsl": "52, 100%, 50%"},
    {"name": "Deep Sapphire", "hex": "#082567", "rgb": "8, 37, 103", "hsl": "220, 86%, 22%"}
]


def generate_color_record() -> dict:
    """Simulates Faker.js color generators (human name, hex, rgb, hsl)."""
    return random.choice(COLOR_DATABASE)


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_color_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for Faker Color controls."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎨 Random Color", callback_data="col_random"),
            InlineKeyboardButton("💎 Emerald Green", callback_data="col_emerald")
        ],
        [
            InlineKeyboardButton("🔥 Sunset Orange", callback_data="col_sunset"),
            InlineKeyboardButton("📚 Color Docs", url="https://fakerjs.dev/api/color.html")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="col_close")]
    ])


@app.on_message(filters.command(["color", "fakercolor", "palette"]))
async def cmd_color_dashboard(client: Client, message: Message):
    """Command: /color - Opens the interactive Faker Color generator dashboard."""
    text = (
        "🎨 **Faker Color Intelligence Suite**\n\n"
        "Generate random CSS color names, HEX codes, RGB arrays, and HSL formats "
        "using the interactive controls below:"
    )
    await message.reply_text(text, reply_markup=get_color_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.command(["fakecolor", "randomcolor"]))
async def cmd_generate_color(client: Client, message: Message):
    """Command: /fakecolor - Generates a complete mock color record."""
    color = generate_color_record()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="col_random")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="col_home")]
    ])

    response_text = (
        f"🎨 **FAKER COLOR SPECIFICATION**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Color Name:** `{color['name']}`\n"
        f"• **HEX Code:** `{color['hex']}`\n"
        f"• **RGB Value:** `rgb({color['rgb']})`\n"
        f"• **HSL Value:** `hsl({color['hsl']})`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await message.reply_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^col_home$"))
async def cb_col_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🎨 **Faker Color Intelligence Suite**\n\n"
        "Generate random CSS color names, HEX codes, RGB arrays, and HSL formats "
        "using the interactive controls below:"
    )
    await query.message.edit_text(text, reply_markup=get_color_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^col_random$"))
async def cb_col_random(client: Client, query: CallbackQuery):
    await query.answer("Generating color record...")
    color = generate_color_record()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="col_random")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="col_home")]
    ])

    response_text = (
        f"🎨 **FAKER COLOR SPECIFICATION**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Color Name:** `{color['name']}`\n"
        f"• **HEX Code:** `{color['hex']}`\n"
        f"• **RGB Value:** `rgb({color['rgb']})`\n"
        f"• **HSL Value:** `hsl({color['hsl']})`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await query.message.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^col_emerald$"))
async def cb_col_emerald(client: Client, query: CallbackQuery):
    await query.answer("Selecting emerald color...")
    color = COLOR_DATABASE[2]

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="col_random")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="col_home")]
    ])

    response_text = (
        f"🎨 **FAKER COLOR SPECIFICATION**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Color Name:** `{color['name']}`\n"
        f"• **HEX Code:** `{color['hex']}`\n"
        f"• **RGB Value:** `rgb({color['rgb']})`\n"
        f"• **HSL Value:** `hsl({color['hsl']})`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await query.message.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^col_sunset$"))
async def cb_col_sunset(client: Client, query: CallbackQuery):
    await query.answer("Selecting sunset orange...")
    color = COLOR_DATABASE[4]

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="col_random")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="col_home")]
    ])

    response_text = (
        f"🎨 **FAKER COLOR SPECIFICATION**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Color Name:** `{color['name']}`\n"
        f"• **HEX Code:** `{color['hex']}`\n"
        f"• **RGB Value:** `rgb({color['rgb']})`\n"
        f"• **HSL Value:** `hsl({color['hsl']})`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await query.message.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^col_close$"))
async def cb_col_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()



# --- MOCK DATA POOLS (Faker.js Food Module Standards) ---
FOOD_DATABASE = [
    {"dish": "Truffle Mushroom Risotto", "ingredient": "Arborio Rice", "spice": "Black Truffle", "category": "Italian", "diet": "Vegetarian"},
    {"dish": "Spicy Seafood Paella", "ingredient": "Tiger Prawns", "spice": "Spanish Saffron", "category": "Spanish", "diet": "Gluten-Free"},
    {"dish": "Miso Glazed Black Cod", "ingredient": "Black Cod Filet", "spice": "White Miso Paste", "category": "Japanese", "diet": "Pescatarian"},
    {"dish": "Classic Margherita Pizza", "ingredient": "San Marzano Tomatoes", "spice": "Fresh Basil", "category": "Italian", "diet": "Vegetarian"},
    {"dish": "Avocado & Quinoa Buddha Bowl", "identity": "Quinoa", "ingredient": "Hass Avocado", "spice": "Cumin", "category": "Fusion", "diet": "Vegan"},
    {"dish": "Wagyu Beef Burger", "ingredient": "Wagyu Beef Patty", "spice": "Smoked Paprika", "category": "American", "diet": "High-Protein"},
    {"dish": "Thai Green Curry", "ingredient": "Bamboo Shoots", "spice": "Lemongrass & Galangal", "category": "Thai", "diet": "Dairy-Free"}
]

BEVERAGES = ["Artisan Matcha Latte", "Sparkling Yuzu Lemonade", "Cold Brew Nitro Coffee", "Botanical Gin Tonic", "Fresh Coconut Water"]


def generate_food_record() -> dict:
    """Simulates Faker.js food generators (dish, ingredient, spice, category, dietary)."""
    item = random.choice(FOOD_DATABASE)
    bev = random.choice(BEVERAGES)
    return {
        "dish": item["dish"],
        "ingredient": item["ingredient"],
        "spice": item["spice"],
        "category": item["category"],
        "diet": item["diet"],
        "pairing": bev,
        "calories": random.randint(350, 850)
    }


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_food_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for Faker Food controls."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🍽️ Random Dish", callback_data="food_random"),
            InlineKeyboardButton("🇮🇹 Italian Special", callback_data="food_italian")
        ],
        [
            InlineKeyboardButton("🌱 Vegan Bowl", callback_data="food_vegan"),
            InlineKeyboardButton("📚 Food Docs", url="https://fakerjs.dev/api/food.html")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="food_close")]
    ])


@app.on_message(filters.command(["food", "fakerfood", "recipe"]))
async def cmd_food_dashboard(client: Client, message: Message):
    """Command: /food - Opens the interactive Faker Food generator dashboard."""
    text = (
        "🍽️ **Faker Food Intelligence Suite**\n\n"
        "Generate random dishes, ingredients, spices, dietary classifications, and beverage pairings "
        "using the interactive controls below:"
    )
    await message.reply_text(text, reply_markup=get_food_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.command(["fakefood", "randomfood"]))
async def cmd_generate_food(client: Client, message: Message):
    """Command: /fakefood - Generates a complete mock culinary recipe record."""
    food = generate_food_record()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="food_random")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="food_home")]
    ])

    response_text = (
        f"🍽️ **FAKER CULINARY RECORD**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Dish Name:** `{food['dish']}`\n"
        f"• **Cuisine Category:** `{food['category']}`\n"
        f"• **Key Ingredient:** `{food['ingredient']}`\n"
        f"• **Signature Spice:** `{food['spice']}`\n"
        f"• **Dietary Tag:** `{food['diet']}`\n"
        f"• **Beverage Pairing:** `{food['pairing']}`\n"
        f"• **Estimated Energy:** `{food['calories']} kcal`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await message.reply_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^food_home$"))
async def cb_food_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🍽️ **Faker Food Intelligence Suite**\n\n"
        "Generate random dishes, ingredients, spices, dietary classifications, and beverage pairings "
        "using the interactive controls below:"
    )
    await query.message.edit_text(text, reply_markup=get_food_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^food_random$"))
async def cb_food_random(client: Client, query: CallbackQuery):
    await query.answer("Generating dish record...")
    food = generate_food_record()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="food_random")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="food_home")]
    ])

    response_text = (
        f"🍽️ **FAKER CULINARY RECORD**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Dish Name:** `{food['dish']}`\n"
        f"• **Cuisine Category:** `{food['category']}`\n"
        f"• **Key Ingredient:** `{food['ingredient']}`\n"
        f"• **Signature Spice:** `{food['spice']}`\n"
        f"• **Dietary Tag:** `{food['diet']}`\n"
        f"• **Beverage Pairing:** `{food['pairing']}`\n"
        f"• **Estimated Energy:** `{food['calories']} kcal`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await query.message.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^food_italian$"))
async def cb_food_italian(client: Client, query: CallbackQuery):
    await query.answer("Selecting Italian dish...")
    food = FOOD_DATABASE[0]
    food["pairing"] = "Chianti Classico Wine"
    food["calories"] = 620

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="food_random")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="food_home")]
    ])

    response_text = (
        f"🍽️ **FAKER CULINARY RECORD**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Dish Name:** `{food['dish']}`\n"
        f"• **Cuisine Category:** `Italian`\n"
        f"• **Key Ingredient:** `{food['ingredient']}`\n"
        f"• **Signature Spice:** `{food['spice']}`\n"
        f"• **Dietary Tag:** `{food['diet']}`\n"
        f"• **Beverage Pairing:** `Chianti Classico Wine`\n"
        f"• **Estimated Energy:** `620 kcal`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await query.message.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^food_vegan$"))
async def cb_food_vegan(client: Client, query: CallbackQuery):
    await query.answer("Selecting vegan dish...")
    food = FOOD_DATABASE[4]
    food["pairing"] = "Sparkling Yuzu Lemonade"
    food["calories"] = 410

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="food_random")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="food_home")]
    ])

    response_text = (
        f"🍽️ **FAKER CULINARY RECORD**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Dish Name:** `{food['dish']}`\n"
        f"• **Cuisine Category:** `Fusion`\n"
        f"• **Key Ingredient:** `{food['ingredient']}`\n"
        f"• **Signature Spice:** `{food['spice']}`\n"
        f"• **Dietary Tag:** `Vegan`\n"
        f"• **Beverage Pairing:** `Sparkling Yuzu Lemonade`\n"
        f"• **Estimated Energy:** `410 kcal`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await query.message.edit_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^food_close$"))
async def cb_food_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
