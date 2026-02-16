import os



class Config:
    API_ID = int(os.environ.get("API_ID", "12345")) # Get from my.telegram.org
    API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
    
    # MongoDB Connection URL (Get from MongoDB Atlas)
    MONGO_URL = os.environ.get("MONGO_URL", "mongodb+srv://...") 
    
    DB_NAME = "GroupSchedulerBot"
    ADMIN_ID = 784589736 # Your Telegram ID (to prevent abuse)
