import aiohttp
import asyncio
import math

def get_price_levels(current_price):
    """Vytvoří cenové úrovně na základě aktuální ceny"""
    level1 = current_price * 0.005  # 0.5%
    level2 = current_price * 0.015  # 1.5%
    level3 = current_price * 0.03   # 3%
    return level1, level2, level3

def aggregate_orders_by_levels(orders, current_price, is_asks=True):
    """Agreguje objednávky podle dynamických cenových úrovní"""
    level1, level2, level3 = get_price_levels(current_price)

    aggregated = {
        "level1": {"orders": [], "range": "0-0.5%"},
        "level2": {"orders": [], "range": "0.5-1.5%"},
        "level3": {"orders": [], "range": "1.5-3%"}
    }

    for price, quantity in orders:
        price_float = float(price)
        quantity_float = float(quantity)
        quantity_usd = quantity_float * price_float
        price_diff = abs(price_float - current_price)
        price_diff_percent = (price_diff / current_price) * 100

        if price_diff_percent <= 0.5:
            aggregated["level1"]["orders"].append((price_float, quantity_usd))
        elif price_diff_percent <= 1.5:
            aggregated["level2"]["orders"].append((price_float, quantity_usd))
        elif price_diff_percent <= 3:
            aggregated["level3"]["orders"].append((price_float, quantity_usd))

    result = []
    for level in aggregated.values():
        if level["orders"]:
            if is_asks:
                min_price = min(order[0] for order in level["orders"])
                total_quantity_usd = sum(order[1] for order in level["orders"])
                result.append((min_price, total_quantity_usd, level["range"]))
            else:
                max_price = max(order[0] for order in level["orders"])
                total_quantity_usd = sum(order[1] for order in level["orders"])
                result.append((max_price, total_quantity_usd, level["range"]))

    return sorted(result, key=lambda x: x[0], reverse=not is_asks)

async def get_binance_liquidity():
    orderbook_url = "https://api.binance.com/api/v3/depth"
    params = {
        "symbol": "AAVEUSDT",
        "limit": 500
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(orderbook_url, params=params, headers=headers) as response:
                orderbook_data = await response.json()

                best_bid = float(orderbook_data['bids'][0][0])
                best_ask = float(orderbook_data['asks'][0][0])
                current_price = (best_bid + best_ask) / 2

                aggregated_asks = aggregate_orders_by_levels(orderbook_data['asks'], current_price, True)
                aggregated_bids = aggregate_orders_by_levels(orderbook_data['bids'], current_price, False)

                return {
                    'exchange': 'Binance',
                    'price': current_price,
                    'orderbook': {
                        'asks': aggregated_asks,
                        'bids': aggregated_bids
                    }
                }
    except Exception as e:
        print(f"Binance API chyba: {e}")
        return None

async def get_okx_liquidity():
    orderbook_url = "https://www.okx.com/api/v5/market/books"
    params = {
        "instId": "AAVE-USDT",
        "sz": "400"
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(orderbook_url, params=params, headers=headers) as response:
                data = await response.json()

                if 'code' in data and data['code'] != '0':
                    raise ValueError(f"OKX API error: {data.get('msg', 'Unknown error')}")

                orderbook_data = data['data'][0]

                bids = [[bid[0], bid[1]] for bid in orderbook_data['bids']]
                asks = [[ask[0], ask[1]] for ask in orderbook_data['asks']]

                best_bid = float(bids[0][0])
                best_ask = float(asks[0][0])
                current_price = (best_bid + best_ask) / 2

                aggregated_asks = aggregate_orders_by_levels(asks, current_price, True)
                aggregated_bids = aggregate_orders_by_levels(bids, current_price, False)

                return {
                    'exchange': 'OKX',
                    'price': current_price,
                    'orderbook': {
                        'asks': aggregated_asks,
                        'bids': aggregated_bids
                    }
                }
    except Exception as e:
        print(f"OKX API chyba: {e}")
        return None

async def get_bybit_liquidity():
    orderbook_url = "https://api.bybit.com/v5/market/orderbook"
    params = {
        "category": "spot",
        "symbol": "AAVEUSDT",
        "limit": 500
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(orderbook_url, params=params, headers=headers) as response:
                data = await response.json()
                orderbook_data = data['result']

                bids = [[bid[0], bid[1]] for bid in orderbook_data['b']]
                asks = [[ask[0], ask[1]] for ask in orderbook_data['a']]

                best_bid = float(bids[0][0])
                best_ask = float(asks[0][0])
                current_price = (best_bid + best_ask) / 2

                aggregated_asks = aggregate_orders_by_levels(asks, current_price, True)
                aggregated_bids = aggregate_orders_by_levels(bids, current_price, False)

                return {
                    'exchange': 'Bybit',
                    'price': current_price,
                    'orderbook': {
                        'asks': aggregated_asks,
                        'bids': aggregated_bids
                    }
                }
    except Exception as e:
        print(f"Bybit API chyba: {e}")
        return None

async def main():
    # Spustíme všechny requesty současně
    tasks = [
        asyncio.create_task(get_binance_liquidity()),
        asyncio.create_task(get_okx_liquidity()),
        asyncio.create_task(get_bybit_liquidity())
    ]

    # Počkáme na dokončení všech requestů
    results = await asyncio.gather(*tasks)
    valid_results = [r for r in results if r is not None]
    ranges = ["0-0.5%", "0.5-1.5%", "1.5-3%"]

    # Agregovaný přehled pro všechny burzy dohromady
    print("\n=== Agregovaný přehled likvidity AAVE/USDT ===")

    print("\nProdejní nabídky (ASKS):")
    total_asks_all = 0
    for range_info in ranges:
        range_total = 0
        for exchange_data in valid_results:
            asks = exchange_data['orderbook']['asks']
            matching_ask = next((ask for ask in asks if ask[2] == range_info), None)
            if matching_ask:
                range_total += matching_ask[1]
        print(f"Pásmo {range_info:<9}: ${range_total:,.2f}")
        total_asks_all += range_total
    print(f"Celkem ASKS: ${total_asks_all:,.2f}")

    print("\nNákupní nabídky (BIDS):")
    total_bids_all = 0
    for range_info in ranges:
        range_total = 0
        for exchange_data in valid_results:
            bids = exchange_data['orderbook']['bids']
            matching_bid = next((bid for bid in bids if bid[2] == range_info), None)
            if matching_bid:
                range_total += matching_bid[1]
        print(f"Pásmo {range_info:<9}: ${range_total:,.2f}")
        total_bids_all += range_total
    print(f"Celkem BIDS: ${total_bids_all:,.2f}")

    print("\n")

if __name__ == "__main__":
    asyncio.run(main())