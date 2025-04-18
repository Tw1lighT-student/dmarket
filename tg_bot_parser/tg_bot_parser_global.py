import logging
from datetime import datetime, timedelta
import os
import time
from dotenv import load_dotenv
from king_of_information import main
import telebot
import threading
import json
from telebot import types

load_dotenv()

TGBOT_TOKEN = os.getenv('TGBOT_TOKEN_PARSER')
# === Настройки ===
BOT_TOKEN = TGBOT_TOKEN
CHAT_ID = '791208536'
bot = telebot.TeleBot(BOT_TOKEN)

is_parsing = False
stop_parsing = False
CHECK_ITEMS_FILE = "check_items.json"

def load_check_items():
    if not os.path.exists(CHECK_ITEMS_FILE):
        return []
    with open(CHECK_ITEMS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_check_items(items):
    with open(CHECK_ITEMS_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

def add_item_to_file(item_name):
    items = load_check_items()
    if item_name in items:
        return False
    items.append(item_name)
    save_check_items(items)
    return True

def remove_item_from_file(item_name):
    items = load_check_items()
    if item_name not in items:
        return False
    items.remove(item_name)
    save_check_items(items)
    return True

from telebot import types

@bot.message_handler(commands=["start"])
def cmd_start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    # Ряды с по 2 кнопки
    row1 = [
        types.KeyboardButton("▶️ Старт парсинга"),
        types.KeyboardButton("⏹️ Остановить парсинг")
    ]
    row2 = [
        types.KeyboardButton("➕ Добавить предмет"),
        types.KeyboardButton("🗑️ Удалить предмет")
    ]

    # Отдельная широкая кнопка
    show_btn = types.KeyboardButton("📋 Показать список предметов")

    # Добавляем по строкам
    markup.row(*row1)
    markup.row(*row2)
    markup.add(show_btn)  # занимает всю строку

    bot.send_message(
        message.chat.id,
        "Выбери действие кнопками ниже:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "▶️ Старт парсинга")
def handle_parse(message):
    global is_parsing, stop_parsing
    if is_parsing:
        bot.reply_to(message, "⏳ Парсинг уже идёт. Подожди...")
        return

    is_parsing = True
    stop_parsing = False
    bot.reply_to(message, "🚀 Постоянный парсинг запущен! Для остановки — /stop_parse")

    def loop_task():
        global is_parsing, stop_parsing
        try:
            while not stop_parsing:
                bot.send_message(message.chat.id, f"🔥 Новая итерация парсинга: {time.ctime()}")
                check_items = load_check_items()
                main(check_items)
                # пауза между запусками (например, 6 часов)
                for _ in range(6*60):  # проверяем флаг каждую секунду
                    if stop_parsing:
                        break
                    time.sleep(60)
        finally:
            is_parsing = False
            bot.send_message(message.chat.id, "🛑 Парсинг окончательно остановлен.")
    threading.Thread(target=loop_task, daemon=True).start()

@bot.message_handler(func=lambda m: m.text == "⏹️ Остановить парсинг")
def handle_stop(message):
    global is_parsing, stop_parsing
    if not is_parsing:
        return bot.reply_to(message, "Парсинг и так не запущен.")
    stop_parsing = True
    bot.reply_to(message, "⏹️ Останавливаю парсинг, сейчас поток завершится…")

@bot.message_handler(func=lambda m: m.text == "➕ Добавить предмет")
def cmd_add_start(message):
    # Шаг 1: спрашиваем, что добавить
    msg = bot.reply_to(message, "✏️ Введи название предмета который хочешь добавить, в формате: Weapon name | Skin name")
    # и говорим боту, что **следующее** сообщение от этого пользователя надо передать в функцию process_add
    bot.register_next_step_handler(msg, process_add_item)

def process_add_item(message):
    item = message.text.strip()
    if '|' not in item:
        return bot.reply_to(message, "❌ Неверный формат: нужно “Weapon name | Skin name”. Попробуй снова через /add_item")
    if add_item_to_file(item):
        bot.reply_to(message, f"✅ Добавлено: «{item}»")
    else:
        bot.reply_to(message, f"⚠️ «{item}» уже в списке.")

@bot.message_handler(func=lambda m: m.text == "🗑️ Удалить предмет")
def cmd_remove_start(message):
    msg = bot.reply_to(message, "✏️ Введи название предмета, который хочешь удалить, в формате: Weapon name | Skin name")
    bot.register_next_step_handler(msg, process_remove_item)

def process_remove_item(message):
    item = message.text.strip()
    if '|' not in item:
        return bot.reply_to(message, "❌ Неверный формат. Используй “Weapon name | Skin name” и команду /remove_item заново.")
    if remove_item_from_file(item):
        bot.reply_to(message, f"🗑️ Удалено: «{item}»")
    else:
        bot.reply_to(message, f"❌ «{item}» не найден в списке.")

@bot.message_handler(func=lambda m: m.text == "📋 Показать список предметов")
def cmd_show(message):
    items = load_check_items()
    if not items:
        bot.reply_to(message, "📭 Список пуст.")
    else:
        text = "📋 Отслеживаемые предметы:\n" + "\n".join(f"• {i}" for i in items)
        bot.reply_to(message, text)

if __name__ == "__main__":
    bot.infinity_polling()
