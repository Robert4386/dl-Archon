import os
import telebot
from telebot import types
import tempfile
import zipfile
import threading
from dotenv import load_dotenv

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
    bot.infinity_polling()

if __name__ == "__main__":
    # Проверка .env файла
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write('TELEGRAM_BOT_TOKEN=ваш_токен_здесь\n')
        print("ℹ️ Создан файл .env - добавьте в него токен бота!")
        exit()

    # Запуск в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("\n🔴 Бот остановлен")
        # Добавьте в конец скрипта (после if __name__ == "__main__":)
if os.getenv('RENDER'):
    # Настройки для работы на Render
    from threading import Event
    Event().wait()  # Бесконечное ожидание для работы веб-сервиса