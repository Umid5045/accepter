import os
from dotenv import load_dotenv

load_dotenv()

# Bot tokeni
BOT_TOKEN = os.getenv("7941352882:AAGOWK2bmXVX4b4od_bNoQtTR5vrBfeJmKs")

# Admin ID lari (bir nechta bo'lishi mumkin)
ADMIN_IDS = [
    int(admin_id) for admin_id in os.getenv("ADMIN_IDS", "7970818314").split(",") if admin_id
]
