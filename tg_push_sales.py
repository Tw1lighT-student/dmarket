import time
from datetime import datetime, timedelta
from defs import screenshot_item
from attr import attributes
from nacl.bindings import crypto_sign
import requests
from urllib.parse import urlencode
from pprint import pprint  # Импортируем функцию, а не модуль
import sqlite3
import logging
import telebot
import io

public_key = 'b44b84488268b45ba3342cff2dbcef43c3d78b35b8d622b069ab3745a0157319'
secret_key = '4f9d8af9b058aa566d4382b0493dd6727a7fdca1abf81e46fd2f414709571a43b44b84488268b45ba3342cff2dbcef43c3d78b35b8d622b069ab3745a0157319'

def send_tg_info(attributes):
    title, exterior, item_float, pattern, category_pattern, tier_pattern, stickers, source_steam, item_picture, price, created_at = attributes
    message_parts = []
    message_parts.append(f"<b>===💸ITEM SOLD💸===</b>\n")
    message_parts.append(f"<b>Наименование:</b> {title}\n")
    if exterior:
        message_parts.append(f"<b>👇Атрибуты предмета</b>")
        message_parts.append(f"Качество: {exterior}")
        message_parts.append(f"Флоат: {item_float}")
        message_parts.append(f"Паттерн: {pattern}\n")
        if category_pattern:
            message_parts.append(f"<b>🔥Уникальный паттерн</b>")
            message_parts.append(f"Категория паттерна: {category_pattern}")
            message_parts.append(f"Тир паттерна: {tier_pattern}\n")

    message_parts.append(f"💰Цена продажи: {price}$")
    message_parts.append(f"⏳Время на продаже: {(datetime.now() - datetime.fromtimestamp(int(created_at))).days} дн.")

    # === Настройки ===
    BOT_TOKEN = '7858736282:AAHGe1atwahzTi_0ZNvxT1CS-ceaXGxwvPo'
    CHAT_ID = '791208536'

    bot = telebot.TeleBot(BOT_TOKEN)

    if not item_picture and item_float:
        item_picture = source_steam(source_steam)

    if item_picture:
        # === Скачиваем изображение в память ===
        response = requests.get(item_picture)

        if response.status_code == 200:
            # Создаём "виртуальный файл" в памяти
            image_bytes = io.BytesIO(response.content)
            image_bytes.name = 'image.jpg'  # Telegram требует имя файла

            # Отправляем как фото
            message = "\n".join(message_parts)
            bot.send_photo(chat_id=791208536, photo=image_bytes, caption=message, parse_mode="HTML")

            # Если хочешь отправить как документ (без сжатия):
            # bot.send_document(chat_id=CHAT_ID, document=image_bytes)
    else:
        message_parts.append(f"<b>Источник:</b> <a href=\"{source_steam}\">Открыть в Steam</a>")
        message = "\n".join(message_parts)
        bot.send_message(chat_id=791208536, text=message, parse_mode="HTML")
        print("Ошибка при скачивании изображения.")

def check_last_sales(public_key, secret_key, username):
    local_logger = logging.getLogger(__name__)
    rootApiUrl = "https://api.dmarket.com"
    now = datetime.now()  # Получаем текущее локальное время
    new_time = now - timedelta(minutes=10000)  # Вычитаем 15 минут
    local_logger.debug(f'Мы ищем предметы до {new_time}')
    unix_limit_time = new_time.timestamp()  # Преобразуем в UNIX-время
    Flag = True
    while Flag:
        params = {
            'limit': '10',
        }
        # получаем данные для X-Request-Sign
        nonce = str(round(datetime.now().timestamp())) # X-Sign-Date
        api_url_path = "/marketplace-api/v1/user-offers/closed?" # Получаем данные
        method = "GET"
        query_string = urlencode(params, doseq=True) # Построение из словаря в URL-кодировку
        string_to_sign = method + api_url_path + query_string + nonce # Построение запроса
        signature_prefix = "dmar ed25519 " # Преписка самого дмаркета (По какому условию делать hash)
        encoded = string_to_sign.encode('utf-8')
        signature_bytes = crypto_sign(encoded, bytes.fromhex(secret_key)) # Сама подпись
        signature_hex = signature_prefix + signature_bytes[:64].hex() # Все соединяем

        headers = {
            "X-Api-Key": public_key,
            "X-Request-Sign": signature_hex,
            "X-Sign-Date": nonce
        }

        market_response = requests.get(rootApiUrl + "/marketplace-api/v1/user-offers/closed?", headers=headers, params=params).json()
        pprint(market_response)
        for item in market_response['Trades']:
            attributes = []
            if unix_limit_time <= int(item['OfferClosedAt']):
                offer_id = item['OfferID']
                # item_title = item['Title']
                # price = item['Price']
                # price_without_comission = float(item['Price']['Amount']) - float(item['Fee']['Amount']['Amount'])

                with sqlite3.connect(f'db/dmarket_data_base_{username}.db', timeout=10) as db:
                    cursor = db.cursor()
                    cursor.execute('''
                        SELECT *
                        FROM items
                        WHERE `offer_id` = ?
                    ''', ('0333b73f-faa3-4498-9441-50a4bb3d0bd1',))
                    title, exterior, item_float, pattern, float_range, category_pattern, tier_pattern, count_sales, stickers, source_steam, item_picture, price, time_on_sale, created_at, offer_id = cursor.fetchone()

                    # cursor.execute('''
                    #     DELETE *
                    #     FROM items
                    #     WHERE `offer_id` = ?
                    # ''', ('0333b73f-faa3-4498-9441-50a4bb3d0bd1',))
                    attributes = [title, exterior, item_float, pattern, category_pattern, tier_pattern, stickers, source_steam, item_picture, price, created_at]
            else:
                Flag = False

            if attributes:
                send_tg_info(attributes)

item_attributes = check_last_sales(public_key, secret_key, username='hard2sell_acc')