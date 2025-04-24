import csv
import time
from datetime import datetime
from collections import defaultdict
from operator import itemgetter
from binance.client import Client
import config

FEE = 0.00075
ITERATIONS = 5000
PRIMARY = ['ETH', 'USDT', 'BTC', 'BNB', 'ADA', 'SOL', 'LINK', 'LTC', 'UNI', 'XTZ']


# ---------- Agents ----------
class PriceAgent:
    def __init__(self, client):
        self.client = client

    def get_prices(self):
        prices = self.client.get_orderbook_tickers()
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


class TriangleAgent:
    def __init__(self):
        self.seen = set()

    def find_triangles(self, prices, base='USDT'):
        for triangle in self._recurse(prices, base, base):
            coins = tuple(triangle['coins'])
            if coins not in self.seen:
                self.seen.add(coins)
                yield triangle

    def _recurse(self, prices, current, start, depth=3, amount=1.0):
        if depth > 0:
            for coin, price in prices.get(current, {}).items():
                new_amount = (amount * price) * (1.0 - FEE)
                for triangle in self._recurse(prices, coin, start, depth - 1, new_amount):
                    triangle['coins'].append(current)
                    yield triangle
        elif current == start and amount > 1.0:
            yield {'coins': [current], 'profit': amount}


class DecisionAgent:
    def __init__(self, min_profit=0.1):
        self.min_profit = min_profit

    def should_trade(self, triangle):
        profit_pct = (triangle['profit'] - 1.0) * 100
        return profit_pct >= self.min_profit


class ExecutionAgent:
    def __init__(self, simulate=True):
        self.simulate = simulate

    def execute(self, triangle):
        if self.simulate:
            print(f"Simulando execução: {triangle}")
        else:
            # Aqui entraria lógica real de execução de ordens
            pass


# ---------- Utilidades ----------
def describe_triangle(prices, triangle, writer):
    coins = triangle['coins'][::-1]
    price_pct = round((triangle['profit'] - 1.0) * 100, 4)
    timestamp = datetime.now()
    print(f"{timestamp} {'->'.join(coins):30} {price_pct}%")
    writer.writerow([timestamp, '->'.join(coins), price_pct])
    for i in range(len(coins) - 1):
        print(f"     {coins[i+1]:4} / {coins[i]:4}: {prices[coins[i]][coins[i+1]]:.8f}")
    print("")


# ---------- Main ----------
def main():
    client = Client(config.API_KEY, config.API_SECRET)

    price_agent = PriceAgent(client)
    triangle_agent = TriangleAgent()
    decision_agent = DecisionAgent(min_profit=0.15)
    execution_agent = ExecutionAgent(simulate=True)

    with open('arbitrage.csv', 'w', newline='', encoding='UTF8') as f:
        writer = csv.writer(f)
        writer.writerow(['Timestamp', 'Path', 'Profit (%)'])

        for _ in range(ITERATIONS):
            prices = price_agent.get_prices()
            triangles = list(triangle_agent.find_triangles(prices))

            for triangle in sorted(triangles, key=itemgetter('profit'), reverse=True):
                if decision_agent.should_trade(triangle):
                    describe_triangle(prices, triangle, writer)
                    execution_agent.execute(triangle)

            time.sleep(1)  # evitar sobrecarga da API


if __name__ == '__main__':
    main()
