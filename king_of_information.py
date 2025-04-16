import logging
import requests
from urllib.parse import urlencode
from nacl.bindings import crypto_sign
import sqlite3
from unicodedata import category
from datetime import datetime, timedelta
import os
import time
from pprint import pprint
from dotenv import load_dotenv
from defs import check_float_level, check_pattern

check_item_final = []
check_item = ['MP9 | Starlight Protector', 'AWP | Acheron']

load_dotenv()

public_key = 'b44b84488268b45ba3342cff2dbcef43c3d78b35b8d622b069ab3745a0157319'
secret_key = os.getenv("SECRET_KEY_HARD2SELL")

def add_item_to_base(title, item_float, pattern, float_range, category_pattern, tier_pattern, price, closed_at, cursor, first_parsed_unix):
    insert_item = [title, item_float, pattern, float_range, category_pattern, tier_pattern, price, closed_at]

    query_add_item = '''INSERT INTO items(title, item_float, pattern, float_range, category_pattern, tier_pattern, price, closed_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)'''

    cursor.execute("""
        INSERT INTO items_check(title, first_parsed_unix)
        VALUES(?, ?)
        ON CONFLICT(title) DO UPDATE SET first_parsed_unix = excluded.first_parsed_unix
    """, (title, first_parsed_unix))

    cursor.execute(query_add_item, insert_item)

def check_first_price_dmarket(item_name):
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

    dmarket_response = requests.get(
        rootApiUrl + f"/exchange/v1/market/items?", params=params).json()

    if dmarket_response['objects']:
        check_item_final.append(item_name)
        local_logger.debug(f'dmarket_response: {dmarket_response}')
        price = float(dmarket_response['objects'][0]['price']['USD']) / 100
    else:
        local_logger.debug('Данного предмета на продаже нет')
        return 0

    return price

def get_special_sales(item_title_clean, price_first_item, item_title, public_key, secret_key, cursor):
    params = {
        'gameId': "a8db",
        'txOperationType': 'Offer',
        'limit': '500',
        'title': item_title
    }

    category_pattern = ''
    float_range = ''
    tier_pattern = ''
    item_float = ''

    setup_logging()
    local_logger = logging.getLogger(__name__)
    rootApiUrl = "https://api.dmarket.com"
    local_logger.debug(f'Принял в обработку данные {params, public_key, secret_key}')
    # Получаем 3-х месячный барьер, до которого мы будем считать продажи
    # now = datetime.now()  # Получаем текущее локальное время
    # new_time = now - timedelta(weeks=13)  # Вычитаем 13 недель +- 3 месяца
    # local_logger.debug(f'Мы ищем предметы до {new_time}')
    # unix_limit_time = new_time.timestamp()  # Преобразуем в UNIX-время

    # получаем данные для X-Request-Sign
    nonce = str(round(datetime.now().timestamp())) # X-Sign-Date
    api_url_path = "/trade-aggregator/v1/last-sales?" # Получаем данные
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

    response = requests.get(rootApiUrl + "/trade-aggregator/v1/last-sales?", headers=headers, params=params)
    local_logger.debug(f'Статус код сайта: {response.status_code}')

    market_response = response.json()
    if response.status_code != 200:
        local_logger.warning(f'Ошибка с взаимодействием сайта: {market_response}')

    count_sales = 0
    # pprint(market_response)
    first_parsed_unix = market_response['sales'][0]['date']
    for item in market_response['sales']:
        if float(item['price']) >= price_first_item * 2:
            if item['offerAttributes']:
                if item['offerAttributes'].get('floatValue', ''):
                    min_float, max_float = check_float_level(item['offerAttributes']['floatValue'])
                    if min_float:
                        float_range = f'{min_float} - {max_float}'
                        item_float = item['offerAttributes']['floatValue']

                if len(item['offerAttributes']) == 2:
                    print(item_title, item['price'], item['offerAttributes'].get('paintSeed', ''), item['offerAttributes']['floatValue'], datetime.fromtimestamp(int(item['date'])))
                    category_pattern, tier_pattern, patterns = check_pattern(item_title_clean, int(item['offerAttributes']['paintSeed']))

                add_item_to_base(item_title, item_float, item['offerAttributes'].get('paintSeed', ''), float_range, category_pattern, tier_pattern, item['price'], datetime.fromtimestamp(int(item['date'])), cursor, first_parsed_unix)
        # if unix_limit_time < float(item['date']):


def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('app.log', mode='w'), # Режим 'w' – перезапись файла
            logging.StreamHandler()
        ]
    )

def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    with sqlite3.connect('db/dmarket_database_big_items.db', timeout=10) as db:
        cursor = db.cursor()

        cursor.execute("DROP TABLE IF EXISTS items")
        # Создание таблицы один раз
        cursor.execute("""CREATE TABLE IF NOT EXISTS items(
            title TEXT NOT NULL,
            item_float TEXT,
            pattern INTEGER,
            float_range TEXT,
            category_pattern TEXT, 
            tier_pattern INTEGER,
            price REAL,
            closed_at TEXT
        )""")

        cursor.execute("DROP TABLE IF EXISTS items_check")
        cursor.execute(""" CREATE TABLE IF NOT EXISTS items_check(
            title TEXT NOT NULL UNIQUE,
            first_parsed_unix INTEGER
        )""")

        for item in check_item:
            for i in [item, 'StatTrak™ ' + item]:
                for exterior in ['(Factory New)', '(Minimal Wear)', '(Field-Tested)', '(Battle-Scarred)']:
                    price_first_item = check_first_price_dmarket(i + exterior)
                    if price_first_item != 0:
                        get_special_sales(item, price_first_item, i + ' ' + exterior, public_key, secret_key, cursor)


                    # if objects:
                    #     check_item.append(i + exterior)
        cursor.execute("SELECT COUNT(*) FROM items")
        print("Добавлено строк в items:", cursor.fetchone()[0])
        db.commit()

if __name__ == "__main__":
    pprint('')
    main()
