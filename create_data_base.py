from defs import setup_logging, delete_data_base, check_float_level, get_special_sales, check_sticker_price, check_pattern, screenshot_item, add_item_to_base, get_username
import sqlite3
from datetime import datetime, timedelta
import time
import requests
from pprint import pprint
import logging
from urllib.parse import urlencode
from nacl.bindings import crypto_sign

public_key = 'b44b84488268b45ba3342cff2dbcef43c3d78b35b8d622b069ab3745a0157319'
secret_key = '4f9d8af9b058aa566d4382b0493dd6727a7fdca1abf81e46fd2f414709571a43b44b84488268b45ba3342cff2dbcef43c3d78b35b8d622b069ab3745a0157319'

def check_show_case(showcase, username):
    start_time = time.time()
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info('Программа запущена')
    logger.debug('Удаляем датабазу')
    rootApiUrl = "https://api.dmarket.com"
    params = {'side': 'market',
        'orderBy': 'personal',
        "orderDir": "desc",
        # "title": '',
        "priceFrom": 0,
        "priceTo": 0,
        "treeFilters": f"sagaAddress[]={showcase}",
        "gameId": "a8db",
        "types": "dmarket",
        "myFavorites": False,
        # "cursor": '',
        "limit": 100,
        "currency": "USD",
        "platform": "browser",
        "isLoggedIn": False}

    delete_data_base(username)

    params_item = {
        'gameId': "a8db",
        'txOperationType': 'Offer',
        'limit': '500',
    }

    while True:
        logger.debug('Запрашиваем данные с сайта')
        dmarket_response = requests.get(
            rootApiUrl + f"/exchange/v1/market/items?", params=params).json()
        if dmarket_response.get('cursor', '') != '':
            params['cursor'] = dmarket_response['cursor']
        else:
            break

        for item in dmarket_response['objects']:
            pattern, float_range, count_sales, stickers_price, exterior, category_pattern, tier_pattern, stickers, source_steam, item_picture  = '', '', '', '', '', '', '', '', '', ''
            title = item['title']
            price = int(item['price']['USD']) / 100
            clean_title = title
            params_item['title'] = title
            logger.debug(f'Новое значение для params_item: {params_item}')
            if 'misc' not in item['extra']['categoryPath']:
                clean_title = title.split(" (")[0]
            logger.debug(f'Название предмета {title}')
            offer_id = item['extra']['offerId']
            item_float = item['extra'].get('floatValue', '')
            if item_float != '':
                exterior = item['extra'].get('exterior')
                min_float, max_float = check_float_level(item_float)
                if min_float:
                    float_range = f'{min_float} - {max_float}'
                pattern = item['extra'].get('paintSeed', '')
                category_pattern, tier_pattern, patterns = check_pattern(clean_title, pattern)
                if category_pattern != '' or min_float != '':
                    if category_pattern != '':
                        count_sales = get_special_sales(patterns, params_item, public_key, secret_key)
                    else:
                        limit_float = [min_float, max_float]
                        count_sales = get_special_sales(limit_float, params_item, public_key, secret_key)
                logger.debug(f'Получено значение count_sales: {count_sales}')
                stickers = item['extra'].get('stickers', '')
                if stickers:
                    # if title[:8] != 'Souvenir':
                    #     stickers_price = check_sticker_price(stickers)
                    sticker_names = [sticker['name'] for sticker in stickers]
                    stickers = ', '.join(sticker_names)
                source_steam = item['extra'].get('inspectInGame', '')
                item_picture = screenshot_item(source_steam)
            created_at = item['createdAt']
            # created_at = datetime.fromtimestamp(item['createdAt'])
            # time_on_sale_days = (datetime.now() - created_at).days
            logger.debug(f'Данные со скина получили: {title, clean_title, exterior, item_float, pattern, float_range, category_pattern, tier_pattern, count_sales, stickers, source_steam, item_picture, price, created_at, offer_id, username}')

            add_item_to_base(title, clean_title, exterior.replace('-', ' ').title(), item_float, pattern, float_range, category_pattern, tier_pattern, count_sales, stickers, source_steam, item_picture, price, created_at, offer_id, username)
    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.debug(f'Elapsed time: {elapsed_time}')

accounts = {'hard2sell_acc': '0x6b475B3Ec5Ec9e485b235aA75B143f968A924000', 'main_acc': '0xd7a144590910F84BB2eC80162c9e45239E83148b'}

for acc in accounts:
    check_show_case(accounts[acc], acc)