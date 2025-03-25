import os
import telebot
from telebot import types
import tempfile
import zipfile
import threading
from dotenv import load_dotenv
from flask import Flask, request
import time

# Загрузка конфигурации
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not TOKEN:
    raise ValueError("Токен бота не найден в .env файле!")

bot = telebot.TeleBot(TOKEN)
user_photos = {}  # {chat_id: [photo_data1, photo_data2, ...]}

# Приветственное сообщение
START_MESSAGE = """
🤖 *Добро пожаловать в dl-Archon Bot!*

Я создан для автоматического скачивания большого объёма данных из Telegram.

🔹 *Как это работает:*
1. Пересылайте мне скриншоты/фото с координатами
2. Я сохраняю все изображения
3. По команде вы можете получить все фото одним архивом

💡 *Основное применение:*
- Автоматизация создания KML-файлов на этапе подготовки папки (чтобы исключить скачивание изображений вручную):
- Это необходимо для последующего OCR-распознования координат и составления KML файла, который можно импортировать в Alpine Quest и т.д.

Просто пришлите мне фото с координатами, и я их сохраню!
"""

# Создаем Flask приложение для работы на Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return '', 403

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Обработчик команды /start"""
    bot.reply_to(message, START_MESSAGE, parse_mode='Markdown')

@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    """Обработчик входящих фото"""
    chat_id = message.chat.id
    
    if chat_id not in user_photos:
        user_photos[chat_id] = []
    
    file_info = bot.get_file(message.photo[-1].file_id)
    user_photos[chat_id].append(bot.download_file(file_info.file_path))
    
    if len(user_photos[chat_id]) == 1:
        send_download_button(chat_id)

def send_download_button(chat_id):
    """Отправляет кнопку для скачивания"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        text=f"📥 Скачать все фото ({len(user_photos[chat_id])} архивом)",
        callback_data="download_photos"
    ))
    bot.send_message(
        chat_id,
        f"✅ Получено {len(user_photos[chat_id])} фото. Нажмите кнопку для скачивания:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == 'download_photos')
def handle_download(call):
    """Обработчик скачивания"""
    chat_id = call.message.chat.id
    
    if not user_photos.get(chat_id):
        bot.answer_callback_query(call.id, "❌ Нет фото для скачивания!")
        return
    
    # Создаем временный ZIP-архив
    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
        with zipfile.ZipFile(tmp_file.name, 'w') as zipf:
            for i, photo_data in enumerate(user_photos[chat_id], 1):
                zipf.writestr(f'coord_photo_{i}.jpg', photo_data)
        
        # Отправляем архив
        with open(tmp_file.name, 'rb') as file_to_send:
            bot.send_document(
                chat_id,
                file_to_send,
                caption=f"📦 Архив с {len(user_photos[chat_id])} фото для Auto-KML"
            )
        
        # Очищаем хранилище
        user_photos[chat_id] = []
        os.unlink(tmp_file.name)
    
    bot.answer_callback_query(call.id, "✔️ Архив успешно отправлен!")

def run_bot():
    """Запускает бота"""
    print("🟢 Бот запущен и готов к работе...")
    if os.getenv('RENDER'):
        # На Render используем webhook
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"https://{os.getenv('RENDER_SERVICE_NAME')}.onrender.com/webhook")
    else:
        # Локально используем polling
        bot.infinity_polling()

if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке
    flask_thread = threading.Thread(
        target=app.run,
        kwargs={'host': '0.0.0.0', 'port': int(os.getenv('PORT', 10000))},
        daemon=True
    )
    flask_thread.start()
    
    # Запускаем бота
    run_bot()