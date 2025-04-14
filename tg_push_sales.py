import time
from datetime import datetime, timedelta
from logging import getLogger
from defs import screenshot_item, setup_logging, check_pattern
from attr import attributes
from nacl.bindings import crypto_sign
import requests
from urllib.parse import urlencode, quote
from pprint import pprint  # Импортируем функцию, а не модуль
import sqlite3
import logging
import telebot
import io
from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY_HARD2SELL = os.getenv("SECRET_KEY_HARD2SELL")
SECRET_KEY_MAIN = os.getenv('SECRET_KEY_MAIN')
AUTH_FLOAT = os.getenv('AUTH_FLOAT')
TGBOT_TOKEN = os.getenv('TGBOT_TOKEN')

def check_first_price_dmarket(item_name, pattern):
    price = 0
    local_logger = logging.getLogger(__name__)
    rootApiUrl = "https://api.dmarket.com"
    params = {'side': 'market',
              'orderBy': 'price',
              "orderDir": "asc",
              "title": item_name,
              "priceFrom": 0,
              "priceTo": 0,
              "gameId": "a8db",
              "types": "dmarket",
              "myFavorites": False,
              # "cursor": '',
              "limit": 1,
              "currency": "USD",
              "platform": "browser",
              "isLoggedIn": False}
    if pattern:
        params["treeFilters"] = f"paintSeed[]={pattern}"
    dmarket_response = requests.get(
        rootApiUrl + f"/exchange/v1/market/items?", params=params).json()

    if len(dmarket_response['objects']) > 0:
        pprint(dmarket_response)
        local_logger.debug(f'dmarket_response: {dmarket_response}')
        if pattern:
            pattern_check = dmarket_response['objects'][0]['extra']['paintSeed']
            local_logger.debug(f'Обрабатываю {pattern_check} паттерн')
        price = float(dmarket_response['objects'][0]['price']['USD']) / 100
    else:
        local_logger.debug('Данного предмета на продаже нет')

    return price


def check_profitable_float(attribute_float):
    setup_logging()
    local_logger = logging.getLogger(__name__)
    headers = {'Authorization': AUTH_FLOAT}
    params = {'sort_by': 'lowest_price',
              'type': 'buy_now'}

    float_value = ''
    final_pattern = ''
    href_float = ''
    profit_ratio = 0
    final_price = 0
    title, float_limit, patterns, max_price, item_pattern = attribute_float
    params['market_hash_name'] = title
    if patterns:
        for pattern in patterns:
            # Блок для нахождения цены на CSFLOAT
            params['paint_seed'] = pattern
            local_logger.debug(f'Конечный params: {params}')
            src = requests.get('https://csfloat.com/api/v1/listings', headers=headers, params=params)
            local_logger.debug(f'Статус сервера: {src.status_code}')
            if src.status_code == 200:
                float_get_data = src.json()
                price = float(float_get_data['data'][0]['price']) / 100
                local_logger.debug(f'Цена предмета на csfloat: {price}')
                    # if price < max_price:
                    #     max_price = price
                    #     final_pattern = pattern
                    #     href_float = 'https://csfloat.com/item/' + float_get_data['data'][0]['id']
            # Блок нахождения цена на Dmarket
            if pattern == item_pattern:
                price_dmarket = max_price
            else:
                price_dmarket = check_first_price_dmarket(title, pattern)
                local_logger.debug(f'price_dmarket для {pattern} паттерна = {price_dmarket}')
                if price_dmarket > max_price:
                    price_dmarket = max_price
            local_logger.debug(f"Коэффициент между ценами данного паттерна между Dmarket'ом ({price_dmarket}) и Csfloat'ом ({price}) равна: {price_dmarket / price}")

            if price_dmarket / price > profit_ratio:
                profit_ratio = price_dmarket / price
                local_logger.debug(f'Обновленный profit_ratio: {profit_ratio} при паттерне {pattern}')
                final_price = price
                final_price_dmarket = price_dmarket
                final_pattern = pattern
                href_float = 'https://csfloat.com/item/' + float_get_data['data'][0]['id']
        if href_float:
            local_logger.debug(f'Конечный href_float: {href_float}')
        else:
            local_logger.debug(f'На данной площадке откупить предмет с данным паттерном не представляется возможным')

    else:
        final_price_dmarket = max_price
        if float_limit:
            min_float, max_float = map(float, float_limit.split(' - '))
            params['max_float'] = max_float

        local_logger.debug(f'Конечный params: {params}')
        src = requests.get('https://csfloat.com/api/v1/listings', headers=headers, params=params)
        local_logger.debug(f'Статус сервера: {src.status_code}')
        if src.status_code == 200:
            float_get_data = src.json()
            if float_get_data['data']:
                href_float = 'https://csfloat.com/item/' + float_get_data['data'][0]['id']
                final_price = float(float_get_data['data'][0]['price']) / 100
                local_logger.debug(f'Конечный href_float: {href_float}')
                profit_ratio = final_price_dmarket / final_price
                if float_limit:
                    float_value = float_get_data['data'][0]['item']['float_value']

    buy_csfloat = [href_float, float_value, final_pattern, final_price, profit_ratio, final_price_dmarket]
    return buy_csfloat

def send_tg_info(attributes, buy_csfloat):
    setup_logging()
    local_logger = logging.getLogger(__name__)
    title, exterior, item_float, pattern, category_pattern, tier_pattern, stickers, source_steam, item_picture, price, created_at = attributes
    logging.debug(f'Получены значения: {title, exterior, item_float, pattern, category_pattern, tier_pattern, stickers, source_steam, item_picture, price, created_at}')
    message_parts = []
    message_parts.append(f"<b>===💸ITEM SOLD💸===</b>\n")
    message_parts.append(f"<b>Наименование:</b> {title}\n")
    if exterior:
        message_parts.append(f"<b>👇Атрибуты предмета</b>")
        message_parts.append(f"Качество: {exterior}")
        message_parts.append(f"Флоат: {item_float:.16f}")
        message_parts.append(f"Паттерн: {pattern}\n")
        if category_pattern:
            message_parts.append(f"<b>🔥Уникальный паттерн</b>")
            message_parts.append(f"Категория паттерна: {category_pattern}")
            message_parts.append(f"Тир паттерна: {tier_pattern}\n")

    message_parts.append(f"💰Цена продажи: {price}$")
    message_parts.append(f"⏳Время на продаже: {(datetime.now() - datetime.fromtimestamp(int(created_at))).days} дн.\n")

    href_float, float_item_float, pattern, price_float, profit_ratio, final_price_dmarket = buy_csfloat

    message_parts.append(f"<b>===Предложения на других сайтах===</b>\n")
    message_parts.append(f"<b>🎯CSFLOAT</b>")
    if float_item_float:
        message_parts.append(f"Float: {float_item_float:.16f}")
    if pattern:
        message_parts.append(f"Pattern: {pattern}")
    message_parts.append(f"Price: {price_float}$\nPrice on Dmarket: {final_price_dmarket}$")
    message_parts.append(f"Профит: x{round(profit_ratio, 2)}")
    message_parts.append(f"<b>Ссылка на предмет:</b> <a href=\"{href_float}\">Открыть</a>")

    # === Настройки ===
    BOT_TOKEN = TGBOT_TOKEN
    CHAT_ID = '791208536'

    bot = telebot.TeleBot(BOT_TOKEN)

    if not item_picture and item_float:
        item_picture = screenshot_item(source_steam)

    if source_steam and item_picture:
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
                # message_parts.append(f"<b>Источник:</b> {source_steam}")
                message = "\n".join(message_parts)
                bot.send_message(chat_id=791208536, text=message, parse_mode="HTML")
    else:
        message = "\n".join(message_parts)
        bot.send_message(chat_id=791208536, text=message, parse_mode="HTML")
        local_logger.debug("Ошибка при скачивании изображения.")

def check_last_sales(public_key, secret_key, username):
    setup_logging()
    local_logger = logging.getLogger(__name__)
    rootApiUrl = "https://api.dmarket.com"
    now = datetime.now()  # Получаем текущее локальное время
    new_time = now - timedelta(minutes=15)  # Вычитаем 15 минутц
    local_logger.debug(f'Мы ищем предметы до {new_time}')
    unix_limit_time = new_time.timestamp()  # Преобразуем в UNIX-время
    Flag = True
    while Flag:
        params = {
            'Limit': '100',
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

        req = requests.get(rootApiUrl + "/marketplace-api/v1/user-offers/closed?", headers=headers, params=params)
        local_logger.debug(req.status_code)
        market_response = req.json()
        local_logger.debug(f'market_response: {market_response}')
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
                    ''', (offer_id,))
                    title, title_clean, exterior, item_float, pattern, float_range, category_pattern, tier_pattern, count_sales, stickers, source_steam, item_picture, price, time_on_sale, created_at, offer_id = cursor.fetchone()

                    # cursor.execute('''
                    #     DELETE *
                    #     FROM items
                    #     WHERE `offer_id` = ?
                    # ''', ('0333b73f-faa3-4498-9441-50a4bb3d0bd1',))
                    patterns = ''
                    if category_pattern:
                        local_logger.debug(f'Предмет с рар паттерном. Категория паттерна: {category_pattern}')
                        _, _, patterns = check_pattern(title_clean, pattern)
                        params = {'side': 'market',
                                  'orderBy': 'price',
                                  "orderDir": "asc",
                                  "title": title,
                                  "priceFrom": 0,
                                  "priceTo": 0,
                                  "gameId": "a8db",
                                  "types": "dmarket",
                                  "myFavorites": False,
                                  # "cursor": '',
                                  "limit": 1,
                                  "currency": "USD",
                                  "platform": "browser",
                                  "isLoggedIn": False}
                        for pattern in patterns:
                            params["treeFilters"] = f"paintSeed[]={pattern}"
                            local_logger.debug(f'Работаю с параметрами: {params}')
                            dmarket_response = requests.get(
                                rootApiUrl + f"/exchange/v1/market/items?", params=params).json()
                            if len(dmarket_response['objects']) > 0:
                                for item in dmarket_response['objects']:
                                    pattern_check = dmarket_response['objects'][0]['extra']['paintSeed']
                                    local_logger.debug(f'Обрабатываю {pattern_check} паттерн')
                                    if item['extra']['sagaAddress'] in [acc['account_key'] for acc in my_profiles.values()]:
                                        local_logger.debug(f'Предмет с данным паттерном уже стоит на продаже на моих аккаунтах, убираю {pattern} из списка для обработки')
                                        patterns.remove(pattern)
                                        break
                                    # elif float(dmarket_response['objects'][0]['price']['USD']) / 100 < price:
                                    #     local_logger.debug('Предмет меньше цены продажи, не рассматриваем')
                                    #     patterns.remove(pattern)
                            else:
                                local_logger.debug('Данного предмета на продаже нет')

                        local_logger.debug(f'Конечный поиск по паттернам: {patterns}')

                    attributes_float = [title, float_range, patterns, price, pattern]
                    buy_csfloat = check_profitable_float(attributes_float)
                    local_logger.debug(f'Получил buy_csfloat: {buy_csfloat}')
                    attributes = [title_clean, exterior, item_float, pattern, category_pattern, tier_pattern, stickers, source_steam, item_picture, price, created_at]
            else:
                Flag = False

            if attributes:
                send_tg_info(attributes, buy_csfloat)


my_profiles = {'main_acc':
                   {"account_key":'0xd7a144590910F84BB2eC80162c9e45239E83148b',
                    'public_key':'f7b1e0984819ceda002bb4e9752f2ad8f710a7b5aedae9440ca43468c3833621',
                    'secret_key':SECRET_KEY_MAIN},
               "hard2sell_acc":
                   {'account_key':"0x6b475B3Ec5Ec9e485b235aA75B143f968A924000",
                    "public_key":'b44b84488268b45ba3342cff2dbcef43c3d78b35b8d622b069ab3745a0157319',
                    "secret_key":SECRET_KEY_HARD2SELL}}
while True:
    for acc_name, acc_data in my_profiles.items():
        public_key = acc_data['public_key']
        secret_key = acc_data['secret_key']

        item_attributes = check_last_sales(public_key, secret_key, acc_name)

    time.sleep(900)

#Задача
#
#Показать мин значение на других площадках данного типа предмета (Пусть это будут даже стикеры, флотовки или паттерн предметы)
#Для баффа - мин значение в обычных продажах, для ксфлоата - обычные продажи + аб, для дмаркета обычные продажи