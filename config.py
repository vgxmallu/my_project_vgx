import os



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
    # Polling interval in seconds (e.g., check feeds every 5 minutes
    UPDATE_INTERVAL = 300 
    
    # Intervals in seconds
    INTERVALS = {"1m": 60, "5m": 300, "20m": 1200, "30m": 1800, "1h": 3600}
    # Auto-delete in seconds (0 = disabled)
    DELETE_TIMES = {"Off": 0, "30s": 30, "300s": 300, "400s": 400, "2400s": 2400}
