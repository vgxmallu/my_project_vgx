import os

DEFAULT_BIRTHDAY_MESSAGE = "🎉 Happy Birthday {mention}! {role} Wishing you an amazing year ahead! 🎂"
DEFAULT_BIRTHDAY_ROLE = "🎂 Birthday Star"

class Config:
    API_ID = int(os.environ.get("API_ID", "12345")) # Get from my.telegram.org
    API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
    
    # MongoDB Connection URL (Get from MongoDB Atlas)
    MONGO_URL = os.environ.get("MONGO_URL", "mongodb+srv://...") 
    
    DB_NAME = "GroupSchedulerBot" # Database name 
    ADMIN_ID = 784589736 # Your Telegram ID (to prevent abuse)
    DEFAULT_INTERVAL = 3600 # Default interval in seconds (3 hours =
    # Viral threshold: 1.5 = 50% higher than average
    VIRAL_THRESHOLD = 1.5 

