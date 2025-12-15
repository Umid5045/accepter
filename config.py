import os
from dotenv import load_dotenv

load_dotenv()

# Bot tokeni
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Admin ID lari (bir nechta bo'lishi mumkin)
ADMIN_IDS = [
    int(admin_id) for admin_id in os.getenv("ADMIN_IDS", "").split(",") if admin_id
]
