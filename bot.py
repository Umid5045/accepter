import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import random
from pathlib import Path

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    ChatMember,
    Chat,
    User
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# Logging konfiguratsiyasi
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Konfiguratsiya
ADMIN_IDS = [123456789]  # Admin ID larini o'zgartiring
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# Papkalar
CHANNELS_DIR = Path("channels")
CHANNELS_DIR.mkdir(exist_ok=True)

# Foydalanuvchilar uchun JSON fayl
USERS_FILE = "users.json"

# Vaqt oralig'lari
ONE_DAY = timedelta(days=1)
ONE_MONTH = timedelta(days=30)

class ChannelManager:
    """Kanal ma'lumotlarini boshqarish"""
    
    @staticmethod
    def get_channel_file(channel_id: str) -> Path:
        return CHANNELS_DIR / f"{channel_id}.json"
    
    @staticmethod
    def save_channel_data(channel_id: str, data: dict):
        file_path = ChannelManager.get_channel_file(channel_id)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def load_channel_data(channel_id: str) -> Optional[dict]:
        file_path = ChannelManager.get_channel_file(channel_id)
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    @staticmethod
    def get_all_channels() -> List[dict]:
        channels = []
        for file in CHANNELS_DIR.glob("*.json"):
            with open(file, 'r', encoding='utf-8') as f:
                channels.append(json.load(f))
        return channels
    
    @staticmethod
    def delete_channel(channel_id: str):
        file_path = ChannelManager.get_channel_file(channel_id)
        if file_path.exists():
            file_path.unlink()

class UserManager:
    """Foydalanuvchi ma'lumotlarini boshqarish"""
    
    @staticmethod
    def load_users() -> Dict:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    @staticmethod
    def save_users(users_data: Dict):
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def add_join_request(user_id: int, channel_id: str):
        users_data = UserManager.load_users()
        
        if str(user_id) not in users_data:
            users_data[str(user_id)] = {}
        
        user_entry = users_data[str(user_id)]
        if channel_id not in user_entry:
            user_entry[channel_id] = []
        
        request_data = {
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        }
        user_entry[channel_id].append(request_data)
        
        # Faqat oxirgi 1000 ta so'rovni saqlash
        if len(user_entry[channel_id]) > 1000:
            user_entry[channel_id] = user_entry[channel_id][-1000:]
        
        UserManager.save_users(users_data)
    
    @staticmethod
    def get_join_requests(channel_id: str, time_range: Optional[timedelta] = None) -> List[int]:
        users_data = UserManager.load_users()
        user_ids = []
        
        for user_id_str, channels in users_data.items():
            if channel_id in channels:
                for request in channels[channel_id]:
                    if request["status"] == "pending":
                        if time_range:
                            request_time = datetime.fromisoformat(request["timestamp"])
                            if datetime.now() - request_time <= time_range:
                                user_ids.append(int(user_id_str))
                        else:
                            user_ids.append(int(user_id_str))
        
        return user_ids

# Admin panel tugmalari
def get_admin_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 Kanallar", callback_data="channels_list")],
        [InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_keyboard():
    keyboard = [
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_channel_keyboard(channel_id: str):
    keyboard = [
        [InlineKeyboardButton("✅ Barchasini qabul qilish", 
                              callback_data=f"accept_all_{channel_id}")],
        [InlineKeyboardButton("🔢 Son bo'yicha qabul qilish", 
                              callback_data=f"accept_count_{channel_id}")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komandasi"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("Siz admin emassiz!")
        return
    
    await update.message.reply_text(
        "👋 Admin panelga xush kelibsiz!",
        reply_markup=get_admin_main_keyboard()
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline tugmalar uchun callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("Siz admin emassiz!")
        return
    
    data = query.data
    
    if data == "cancel":
        await query.edit_message_text(
            "❌ Amal bekor qilindi.",
            reply_markup=get_admin_main_keyboard()
        )
    
    elif data == "channels_list":
        await show_channels_list(query)
    
    elif data == "add_channel":
        await request_channel_id(query)
    
    elif data.startswith("channel_"):
        channel_id = data.split("_")[1]
        await show_channel_details(query, channel_id)
    
    elif data.startswith("accept_all_"):
        channel_id = data.split("_")[2]
        await accept_all_requests(query, channel_id, context)
    
    elif data.startswith("accept_count_"):
        channel_id = data.split("_")[2]
        await request_accept_count(query, channel_id)

async def show_channels_list(query):
    """Ulangan kanallar ro'yxatini ko'rsatish"""
    channels = ChannelManager.get_all_channels()
    
    if not channels:
        keyboard = [[InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")]]
        await query.edit_message_text(
            "📭 Hozircha kanallar mavjud emas.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    buttons = []
    for channel in channels:
        channel_name = channel.get("title", "Noma'lum")
        button_text = f"📢 {channel_name}"
        buttons.append([InlineKeyboardButton(
            button_text, 
            callback_data=f"channel_{channel['id']}"
        )])
    
    buttons.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")])
    
    await query.edit_message_text(
        "📊 Ulangan kanallar:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def request_channel_id(query):
    """Kanal ID sini so'rash"""
    await query.edit_message_text(
        "📝 Kanalning Chat ID sini yuboring:\n\n"
        "ℹ️ Kanal ID sini olish uchun:\n"
        "1. Kanalga @username_to_id botini qo'shing\n"
        "2. Yoki kanal linkidan foydalaning (t.me/joinchat/...)\n\n"
        "⚠️ Bot kanalda admin bo'lishi kerak!",
        reply_markup=get_cancel_keyboard()
    )

async def process_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kanal ID sini qayta ishlash"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    
    try:
        channel_id = update.message.text.strip()
        
        # Chat ID tekshirish
        if not channel_id.startswith('-100'):
            await update.message.reply_text(
                "❌ Noto'g'ri Chat ID format!\n"
                "Kanal Chat ID -100 bilan boshlanishi kerak.",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        # Kanal ma'lumotlarini olish
        try:
            chat = await context.bot.get_chat(int(channel_id))
            
            # Bot adminligini tekshirish
            bot_member = await context.bot.get_chat_member(
                chat_id=int(channel_id),
                user_id=context.bot.id
            )
            
            is_admin = bot_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Tasdiqlash", 
                                       callback_data=f"confirm_{channel_id}"),
                    InlineKeyboardButton("❌ Bekor qilish", 
                                       callback_data="cancel")
                ]
            ]
            
            await update.message.reply_text(
                f"📋 Kanal ma'lumotlari:\n\n"
                f"📛 Nomi: {chat.title}\n"
                f"🔗 Username: @{chat.username if chat.username else 'Yoq'}\n"
                f"🆔 ID: {chat.id}\n"
                f"🤖 Bot admini: {'✅ Ha' if is_admin else '❌ Yoq'}\n\n"
                f"Kanalni qo'shishni tasdiqlaysizmi?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            # Contextga vaqtincha ma'lumot saqlash
            context.user_data['pending_channel'] = {
                'id': str(chat.id),
                'title': chat.title,
                'username': chat.username,
                'is_admin': is_admin
            }
            
        except Exception as e:
            logger.error(f"Kanal ma'lumotlarini olishda xato: {e}")
            await update.message.reply_text(
                "❌ Kanal ma'lumotlarini olishda xatolik!\n"
                "Kanal ID ni tekshiring yoki botni kanalga admin qiling.",
                reply_markup=get_cancel_keyboard()
            )
            
    except ValueError:
        await update.message.reply_text(
            "❌ Noto'g'ri format! Faqat raqam kiriting.",
            reply_markup=get_cancel_keyboard()
        )

async def confirm_channel(query, channel_id: str, context: ContextTypes.DEFAULT_TYPE):
    """Kanalni qo'shishni tasdiqlash"""
    channel_data = context.user_data.get('pending_channel')
    
    if not channel_data or str(channel_data['id']) != channel_id:
        await query.edit_message_text(
            "❌ Ma'lumotlar topilmadi!",
            reply_markup=get_admin_main_keyboard()
        )
        return
    
    # Kanal ma'lumotlarini saqlash
    save_data = {
        'id': channel_data['id'],
        'title': channel_data['title'],
        'username': channel_data['username'],
        'added_date': datetime.now().isoformat(),
        'is_bot_admin': channel_data['is_admin']
    }
    
    ChannelManager.save_channel_data(channel_data['id'], save_data)
    
    await query.edit_message_text(
        f"✅ Kanal muvaffaqiyatli qo'shildi!\n\n"
        f"📛 Nomi: {channel_data['title']}",
        reply_markup=get_admin_main_keyboard()
    )
    
    # Vaqtincha ma'lumotlarni tozalash
    context.user_data.pop('pending_channel', None)

async def show_channel_details(query, channel_id: str):
    """Kanal tafsilotlarini ko'rsatish"""
    channel_data = ChannelManager.load_channel_data(channel_id)
    
    if not channel_data:
        await query.edit_message_text(
            "❌ Kanal topilmadi!",
            reply_markup=get_admin_main_keyboard()
        )
        return
    
    # Statistikani hisoblash
    pending_users = UserManager.get_join_requests(channel_id)
    daily_requests = UserManager.get_join_requests(channel_id, ONE_DAY)
    monthly_requests = UserManager.get_join_requests(channel_id, ONE_MONTH)
    
    # Bot adminligini tekshirish (real vaqtda)
    try:
        bot_member = await query.bot.get_chat_member(
            chat_id=int(channel_id),
            user_id=query.bot.id
        )
        is_admin = bot_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except:
        is_admin = False
    
    text = (
        f"📊 Kanal statistikasi:\n\n"
        f"📛 Nomi: {channel_data.get('title', 'Noma\'lum')}\n"
        f"🔗 Username: @{channel_data.get('username', 'Yoq')}\n"
        f"🆔 ID: {channel_data['id']}\n"
        f"🤖 Bot admini: {'✅ Ha' if is_admin else '❌ Yoq'}\n\n"
        f"📈 Statistika:\n"
        f"• Kutilayotgan so'rovlar: {len(pending_users)} ta\n"
        f"• Oxirgi 24 soat: {len(daily_requests)} ta\n"
        f"• Oxirgi 30 kun: {len(monthly_requests)} ta\n\n"
        f"⬇️ Amallarni tanlang:"
    )
    
    await query.edit_message_text(
        text,
        reply_markup=get_channel_keyboard(channel_id)
    )

async def accept_all_requests(query, channel_id: str, context: ContextTypes.DEFAULT_TYPE):
    """Barcha so'rovlarni qabul qilish"""
    pending_users = UserManager.get_join_requests(channel_id)
    
    if not pending_users:
        await query.edit_message_text(
            "📭 Kutilayotgan so'rovlar yo'q!",
            reply_markup=get_admin_main_keyboard()
        )
        return
    
    # Bot adminligini tekshirish
    try:
        bot_member = await query.bot.get_chat_member(
            chat_id=int(channel_id),
            user_id=query.bot.id
        )
        if bot_member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            await query.edit_message_text(
                "❌ Bot kanalda admin emas!",
                reply_markup=get_admin_main_keyboard()
            )
            return
    except Exception as e:
        logger.error(f"Adminlik tekshirishda xato: {e}")
        await query.edit_message_text(
            "❌ Kanalga kirishda xatolik!",
            reply_markup=get_admin_main_keyboard()
        )
        return
    
    # Foydalanuvchilarni qo'shish
    successful = 0
    failed = 0
    
    await query.edit_message_text(f"⏳ Foydalanuvchilar qo'shilmoqda...")
    
    for user_id in pending_users:
        try:
            await context.bot.approve_chat_join_request(
                chat_id=int(channel_id),
                user_id=user_id
            )
            successful += 1
        except Exception as e:
            logger.error(f"Foydalanuvchini qo'shishda xato {user_id}: {e}")
            failed += 1
    
    # Natijani chiqarish
    await query.edit_message_text(
        f"✅ So'rovlar qabul qilindi!\n\n"
        f"✅ Muvaffaqiyatli: {successful} ta\n"
        f"❌ Muvaffaqiyatsiz: {failed} ta\n"
        f"📊 Jami: {len(pending_users)} ta",
        reply_markup=get_admin_main_keyboard()
    )

async def request_accept_count(query, channel_id: str):
    """Qabul qilish sonini so'rash"""
    await query.edit_message_text(
        "🔢 Qancha foydalanuvchini qabul qilmoqchisiz?\n"
        "Sonni kiriting:",
        reply_markup=get_cancel_keyboard()
    )
    
    # Contextga kanal ID ni saqlash
    query.message.chat.id = query.message.chat.id
    query.message.message_id = query.message.message_id
    
    from telegram.ext import ConversationHandler
    context = query.message._context
    
    context.user_data['accept_count_channel'] = channel_id

async def process_accept_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sonni qayta ishlash va foydalanuvchilarni qabul qilish"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    
    try:
        count = int(update.message.text.strip())
        channel_id = context.user_data.get('accept_count_channel')
        
        if not channel_id:
            await update.message.reply_text(
                "❌ Xatolik! Qaytadan boshlang.",
                reply_markup=get_admin_main_keyboard()
            )
            return
        
        if count <= 0:
            await update.message.reply_text(
                "❌ Son 0 dan katta bo'lishi kerak!",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        # Bot adminligini tekshirish
        try:
            bot_member = await context.bot.get_chat_member(
                chat_id=int(channel_id),
                user_id=context.bot.id
            )
            if bot_member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
                await update.message.reply_text(
                    "❌ Bot kanalda admin emas!",
                    reply_markup=get_admin_main_keyboard()
                )
                return
        except Exception as e:
            logger.error(f"Adminlik tekshirishda xato: {e}")
            await update.message.reply_text(
                "❌ Kanalga kirishda xatolik!",
                reply_markup=get_admin_main_keyboard()
            )
            return
        
        # Foydalanuvchilarni olish
        pending_users = UserManager.get_join_requests(channel_id)
        
        if not pending_users:
            await update.message.reply_text(
                "📭 Kutilayotgan so'rovlar yo'q!",
                reply_markup=get_admin_main_keyboard()
            )
            return
        
        # Tasodifiy foydalanuvchilarni tanlash
        count = min(count, len(pending_users))
        selected_users = random.sample(pending_users, count)
        
        # Foydalanuvchilarni qo'shish
        successful = 0
        failed = 0
        
        processing_msg = await update.message.reply_text(f"⏳ {count} ta foydalanuvchi qo'shilmoqda...")
        
        for user_id in selected_users:
            try:
                await context.bot.approve_chat_join_request(
                    chat_id=int(channel_id),
                    user_id=user_id
                )
                successful += 1
            except Exception as e:
                logger.error(f"Foydalanuvchini qo'shishda xato {user_id}: {e}")
                failed += 1
        
        # Natijani chiqarish
        await processing_msg.edit_text(
            f"✅ {count} ta foydalanuvchidan {successful} tasi qabul qilindi!\n\n"
            f"✅ Muvaffaqiyatli: {successful} ta\n"
            f"❌ Muvaffaqiyatsiz: {failed} ta\n"
            f"📊 Jami so'rov: {len(pending_users)} ta",
            reply_markup=get_admin_main_keyboard()
        )
        
        # Contextni tozalash
        context.user_data.pop('accept_count_channel', None)
        
    except ValueError:
        await update.message.reply_text(
            "❌ Noto'g'ri format! Faqat raqam kiriting.",
            reply_markup=get_cancel_keyboard()
        )

async def handle_chat_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chat join request ni qayd qilish"""
    chat_join_request = update.chat_join_request
    
    user_id = chat_join_request.from_user.id
    chat_id = str(chat_join_request.chat.id)
    
    # So'rovni ma'lumotlar bazasiga qo'shish
    UserManager.add_join_request(user_id, chat_id)
    
    # Kanal ma'lumotlarini yangilash (agar yo'q bo'lsa)
    channel_data = ChannelManager.load_channel_data(chat_id)
    if not channel_data:
        try:
            chat = await context.bot.get_chat(int(chat_id))
            bot_member = await context.bot.get_chat_member(
                chat_id=int(chat_id),
                user_id=context.bot.id
            )
            
            save_data = {
                'id': chat_id,
                'title': chat.title,
                'username': chat.username,
                'added_date': datetime.now().isoformat(),
                'is_bot_admin': bot_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
            }
            
            ChannelManager.save_channel_data(chat_id, save_data)
            
            # Adminlarga bildirishnoma
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        admin_id,
                        f"📥 Yangi so'rov qabul qilindi:\n\n"
                        f"👤 Foydalanuvchi: {chat_join_request.from_user.mention_html()}\n"
                        f"📢 Kanal: {chat.title}\n"
                        f"🆔 Kanal ID: {chat_id}",
                        parse_mode='HTML'
                    )
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"Kanal ma'lumotlarini saqlashda xato: {e}")

def main():
    """Asosiy dastur"""
    # Application yaratish
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlerlar
    application.add_handler(CommandHandler("start", start))
    
    # Callback handler
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Channel ID qabul qilish
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r'^-100\d+$'),
        process_channel_id
    ))
    
    # Qabul qilish sonini qabul qilish
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r'^\d+$'),
        process_accept_count
    ))
    
    # Chat join request handler
    application.add_handler(MessageHandler(
        filters.StatusUpdate.CHAT_JOIN_REQUEST,
        handle_chat_join_request
    ))
    
    # Botni ishga tushirish
    print("🤖 Bot ishga tushdi...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()bot
