import sqlite3
from unicodedata import category
from datetime import datetime, timedelta
import time
import requests
from pprint import pprint
import logging
from urllib.parse import urlencode
from nacl.bindings import crypto_sign

def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('app.log', mode='w'), # Режим 'w' – перезапись файла
            logging.StreamHandler()
        ]
    )

def delete_data_base(username):
    with sqlite3.connect(f'db/dmarket_data_base_{username}.db', timeout=10) as db:
        cursor = db.cursor()
        cursor.execute("""DROP TABLE IF EXISTS items""")

def add_item_to_base(title, title_clean, exterior, item_float, pattern, float_range, category_pattern, tier_pattern, count_sales, stickers, source_steam, item_picture, price, created_at, offer_id, username):
    insert_item = [title, title_clean, exterior, item_float, pattern, float_range, category_pattern, tier_pattern, count_sales, stickers, source_steam, item_picture, price, '', created_at, offer_id]

    with sqlite3.connect(f'db/dmarket_data_base_{username}.db', timeout=10) as db:
        cursor = db.cursor()
        query = """ CREATE TABLE IF NOT EXISTS items(
            title TEXT NOT NULL,
            title_clean TEXT,
            exterior TEXT,
            item_float REAL,
            pattern INTEGER,
            float_range TEXT,
            category_pattern TEXT, 
            tier_pattern INTEGER,
            count_sales INTEGER,
            stickers TEXT,
            source_steam TEXT,
            item_picture TEXT,
            price REAL,
            time_on_sale_days INTEGER, 
            created_at TEXT,
            offer_id TEXT
        )"""
        query_add_item = '''INSERT INTO items(title, title_clean, exterior, item_float, pattern, float_range, category_pattern, tier_pattern, count_sales, stickers, source_steam, item_picture, price, time_on_sale_days, created_at, offer_id) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''

        cursor.execute(query)
        cursor.execute(query_add_item, insert_item)
        db.commit()

def check_sticker_price(stickers):
    local_logger = logging.getLogger(__name__)
    local_logger.debug(f'Обрабатываю стикеры: {stickers}')
    total_price = 0
    params = {
        'country': 'MD',
        'currency': 1,
        'appid': 730
    }
    for sticker in stickers:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}  # Сюда закидываем свой User-Agent (Находится через API (F12))
        title = sticker['name']
        params['market_hash_name'] = f'Sticker | {title}'
        local_logger.debug(f'Обрабатываю Sticker | {title}')
        url_params = urlencode(params, doseq=True)  # Построение из словаря в URL-кодировку
        get_data = requests.get('https://steamcommunity.com/market/priceoverview/?', params=params, headers=headers).json()
        local_logger.debug(f'Данные, которые передал сайт: {get_data}')
        if get_data.get('median_price', 'None') != 'None':
            sticker_price = get_data['median_price']
        elif get_data.get('lowest_price', 'None') != 'None':
            sticker_price = get_data['lowest_price']
        else:
            sticker_price = 'Стикер не продается'

        if sticker_price != 'Стикер не продается':
            sticker_price = sticker_price.split(" ")[0][1:]
            total_price += float(sticker_price)

        time.sleep(3)
    return total_price

def check_float_level(item_float):
    setup_logging()
    local_logger = logging.getLogger(__name__)
    local_logger.debug(f'Принял на обработку флоат {item_float}')
    factory_new = [0, 0.00001, 0.00003, 0.00007, 0.0001, 0.0002, 0.0003, 0.0007, 0.001, 0.002, 0.003, 0.007, 0.01]
    minimal_wear = [0.07, 0.071, 0.075, 0.08]
    field_tested = [0.15, 0.151, 0.155, 0.16, 0.18, 0.21]
    well_worn = [0.38, 0.39]
    battle_scarred = [0.99, 0.999, 1]
    if 0 < item_float < 0.07:
        exterior = factory_new
    elif 0.07 < item_float < 0.15:
        exterior = minimal_wear
    elif 0.15 < item_float < 0.38:
        exterior = field_tested
    elif 0.38 < item_float < 0.45:
        exterior = well_worn
    elif 0.45 < item_float:
        exterior = battle_scarred
    local_logger.debug(f'Ищем доп. атрибуты у предмета в качестве {exterior}')

    for i in range(len(exterior)):
        if exterior[i] <= item_float < exterior[i+1]:
            local_logger.debug(f'Предмет с доп. атрибутами! Предмет был обозначен в рамки от {exterior[i]} до {exterior[i+1]}')
            return exterior[i], exterior[i+1]
        if exterior[i+1] == exterior[-1]:
            local_logger.debug(f'Рамки флоата {item_float} не был найден в {exterior}, значит от без доп. атрибутов')
            return '', ''

def get_special_sales(attributes, params, public_key, secret_key):
    setup_logging()
    local_logger = logging.getLogger(__name__)
    rootApiUrl = "https://api.dmarket.com"
    local_logger.debug(f'Принял в обработку данные {attributes, params, public_key, secret_key}')
    # Получаем 3-х месячный барьер, до которого мы будем считать продажи
    now = datetime.now()  # Получаем текущее локальное время
    new_time = now - timedelta(weeks=13)  # Вычитаем 13 недель +- 3 месяца
    local_logger.debug(f'Мы ищем предметы до {new_time}')
    unix_limit_time = new_time.timestamp()  # Преобразуем в UNIX-время

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
    for item in market_response['sales']:
        if unix_limit_time < float(item['date']):
            if isinstance(attributes[0], int):
                item_pattern = item['offerAttributes'].get('paintSeed', 'None') # Это нужно для паттернов, что нам пригодится попозже
                if item_pattern in attributes:
                    count_sales += 1
            else:
                item_float = item['offerAttributes'].get('floatValue', 'None')
                if item_float != 'None':
                    if attributes[0] < item_float < attributes[1]:
                        count_sales += 1
                else:
                    local_logger.debug(f'Информация о предмета, о котором не получили флоат: {item}')

    return count_sales

def check_pattern(item_title, pattern):
    setup_logging()
    local_logger = logging.getLogger(__name__)
    with sqlite3.connect('db/db_patterns.db') as database:
        cursor = database.cursor()
        cursor.execute("SELECT title FROM Items WHERE title = ?", [item_title])
        title = cursor.fetchone()

        # if not title:
        #     logging.debug('Предмета нет в базе')
        #     return None, None

        cursor.execute('''
            SELECT `Категория паттерна`, `Тир паттерна`
            FROM PatternOverview
            WHERE `Название предмета` = ? AND `Сам паттерн` = ?
        ''', (item_title, pattern))  # Пример для Glock-18 и паттерна 302

        result = cursor.fetchone()

        if result:
            category_pattern, tier = result
            cursor.execute("""
                    SELECT `Сам паттерн`
                    FROM PatternOverview
                    WHERE `Название предмета` = ?
                      AND `Категория паттерна` = ?
                      AND `Тир паттерна` = ?
                """, (item_title, category_pattern, tier))
            patterns = [row[0] for row in cursor.fetchall()]
            local_logger.debug(f'Паттерн {pattern} находится в семействе {category_pattern}: {patterns}')
        else:
            category_pattern, tier, patterns = '', '', ''  # или другие значения по умолчанию

        return category_pattern, tier, patterns


def screenshot_item(source_steam):
    local_logger = logging.getLogger(__name__)
    local_logger.debug(f'Обрабатываю ссылку: {source_steam}')
    source_steam = source_steam.replace('%20', ' ')
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}  # Сюда закидываем свой User-Agent (Находится через API (F12))
    data = {'inspectLink': source_steam}
    while True:
        screen_url = requests.post('https://api.swap.gg/v2/screenshot', json=data, headers=headers).json()
        local_logger.debug(f'Данные с сайта: {screen_url}')
        if screen_url['status'] != 'INTERNAL_ERROR' and screen_url['status'] != 'RATE_LIMIT':
            image_id = screen_url['result']['imageId']
            return f'https://s.swap.gg/{image_id}.jpg'
        else:
            site_answer = screen_url['status']
            local_logger.warning(f'Ошибка при работе с сайтом: {site_answer}')

        return ''

def get_username(public_key, secret_key):
    local_logger = logging.getLogger(__name__)
    rootApiUrl = "https://api.dmarket.com"
    # получаем данные для X-Request-Sign
    nonce = str(round(datetime.now().timestamp()))  # X-Sign-Date
    api_url_path = "/account/v1/user"  # Получаем данные
    method = "GET"
    string_to_sign = method + api_url_path + nonce  # Построение запроса
    signature_prefix = "dmar ed25519 "  # Преписка самого дмаркета (По какому условию делать hash)
    encoded = string_to_sign.encode('utf-8')
    signature_bytes = crypto_sign(encoded, bytes.fromhex(secret_key))  # Сама подпись
    signature_hex = signature_prefix + signature_bytes[:64].hex()  # Все соединяем

    headers = {
        "X-Api-Key": public_key,
        "X-Request-Sign": signature_hex,
        "X-Sign-Date": nonce
    }

    response = requests.get(rootApiUrl + '/account/v1/user?', headers=headers)
    local_logger.debug(f'Статус код сайта: {response.status_code}')

    market_response = response.json()
    if response.status_code != 200:
        local_logger.warning(f'Ошибка с взаимодействием сайта: {market_response}')

    return market_response['username']

# Логирование ✅
# Датабаза для каждого предмета (Нужно ли?)
# Название ✅
# Качество ✅
# Флоат ✅
# Цена ✅
# В каком диапазоне флоат ✅
# Паттерн ✅
# Если паттерн входит в базу по паттернам (которую создам вручную) -> Указать, какого вида этот паттерн ✅
# Стикеры ✅
# Цена стикеров ✅
# Когда был выставлен предмет на продажу ✅
# ?Сколько предмет висит на продаже в днях? ✅
# Сколько продаж в среднем за N промежуток (Пусть будет 3 месяца) ✅ (Добавь ток в базу) + Паттерны ✅
# Ссылку на предмет осмотра в стиме ✅
# Ссылка на сриншот предмета на скриншот скинпорте (или другом сайте который выполняет такую же функцию) ✅❌ (Ибо я не знаю почему, но некоторые ссылки ни скинпорт, ни свагг не могут обработать, но больше 50% они все таки могут обработать)
# Если предмет в "обычном диапазоне" - не считать ✅

#Работа с прокси
#Работа с тг ботом