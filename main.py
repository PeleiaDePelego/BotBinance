from collections import defaultdict
from operator import itemgetter
from datetime import datetime
from time import time
from binance.client import Client
import os
import csv
import requests

FEE = 0.00075
ITERATIONS = 5000
PRIMARY = ['ETH', 'USDT', 'BTC', 'BNB', 'ADA', 'SOL', 'LINK', 'LTC', 'UNI', 'XTZ']

API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
client = Client(API_KEY, API_SECRET)

def get_public_ip():
    try:
        ip = requests.get('https://api64.ipify.org').text
        print(f'IP público do servidor: {ip}')
    except Exception as e:
        print(f'Erro ao obter IP público: {e}')

def main():
    get_public_ip()  # <- Aqui mostramos o IP do Render nos logs
    start_time = time()
    csvfile = open('arbitrage.csv', 'w', newline='', encoding='UTF8')
    result_writer = csv.writer(csvfile, delimiter=',')

    n = 0
    while n < ITERATIONS:
        n += 1
        prices = get_prices()
        triangles = list(find_triangles(prices))
        if triangles:
            for triangle in sorted(triangles, key=itemgetter('profit'), reverse=True):
                describe_triangle(prices, triangle, result_writer)
            print('________')

def get_prices():
    prices = client.get_orderbook_tickers()
    prepared = defaultdict(dict)
    for ticker in prices:
        pair = ticker['symbol']
        ask = float(ticker['askPrice'])
        bid = float(ticker['bidPrice'])
        if ask == 0.0:
            continue
        for primary in PRIMARY:
            if pair.endswith(primary):
                secondary = pair[:-len(primary)]
                prepared[primary][secondary] = 1 / ask
                prepared[secondary][primary] = bid
    return prepared

def find_triangles(prices):
    triangles = []
    starting_coin = 'USDT'
    for triangle in recurse_triangle(prices, starting_coin, starting_coin):
        coins = set(triangle['coins'])
        if not any(prev_triangle == coins for prev_triangle in triangles):
            yield triangle
            triangles.append(coins)
    starting_coin = 'BUSD'
    for triangle in recurse_triangle(prices, starting_coin, starting_coin):
        coins = set(triangle['coins'])
        if not any(prev_triangle == coins for prev_triangle in triangles):
            yield triangle
            triangles.append(coins)

def recurse_triangle(prices, current_coin, starting_coin, depth_left=3, amount=1.0):
    if depth_left > 0:
        pairs = prices[current_coin]
        for coin, price in pairs.items():
            new_price = (amount * price) * (1.0 - FEE)
            for triangle in recurse_triangle(prices, coin, starting_coin, depth_left - 1, new_price):
                triangle['coins'] = triangle['coins'] + [current_coin]
                yield triangle
    elif current_coin == starting_coin and amount > 1.0:
        yield {
            'coins': [current_coin],
            'profit': amount
        }

def describe_triangle(prices, triangle, result_writer):
    coins = triangle['coins']
    price_percentage = (triangle['profit'] - 1.0) * 100
    print(f"{datetime.now()} {'->'.join(coins):26} {round(price_percentage, 4):-7}% profit")
    result_writer.writerow([datetime.now(), '->'.join(coins), round(price_percentage, 4)])
    for i in range(len(coins) - 1):
        first = coins[i]
        second = coins[i + 1]
        print(f"     {second:4} / {first:4}: {prices[first][second]:-17.8f}")
    print('')

if __name__ == '__main__':
    main()
