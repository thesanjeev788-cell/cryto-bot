import ccxt
import pandas as pd
import requests
import os

# ===== TELEGRAM =====
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

# ===== BINANCE USDT FUTURES =====
exchange = ccxt.binanceusdm({
    'enableRateLimit': True
})

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": message})

# ===== TOP 50 USDT FUTURES BY VOLUME =====
def get_top_50_futures():
    markets = exchange.load_markets()
    tickers = exchange.fetch_tickers()
    futures_pairs = []

    for symbol in markets:
        if symbol.endswith("/USDT") and markets[symbol]['active']:
            if symbol in tickers:
                volume = tickers[symbol].get('quoteVolume', 0)
                futures_pairs.append((symbol, volume))

    futures_pairs.sort(key=lambda x: x[1], reverse=True)
    return [pair[0] for pair in futures_pairs[:50]]

# ===== STRATEGY =====
def check_pair(symbol):
    try:
        # 1H Trend (200 EMA)
        ohlc_1h = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=250)
        df1h = pd.DataFrame(ohlc_1h, columns=['t','o','h','l','c','v'])
        df1h['ema200'] = df1h['c'].ewm(span=200).mean()

        trend_up = df1h['c'].iloc[-2] > df1h['ema200'].iloc[-2]
        trend_down = df1h['c'].iloc[-2] < df1h['ema200'].iloc[-2]

        # 30M MACD
        ohlc_30m = exchange.fetch_ohlcv(symbol, timeframe='30m', limit=100)
        df30 = pd.DataFrame(ohlc_30m, columns=['t','o','h','l','c','v'])

        df30['macd'] = df30['c'].ewm(span=12).mean() - df30['c'].ewm(span=26).mean()
        df30['signal'] = df30['macd'].ewm(span=9).mean()

        # Ignore running candle (use closed candles)
        macd_3 = df30['macd'].iloc[-4]
        macd_2 = df30['macd'].iloc[-3]
        macd_1 = df30['macd'].iloc[-2]

        signal_3 = df30['signal'].iloc[-4]
        signal_2 = df30['signal'].iloc[-3]
        signal_1 = df30['signal'].iloc[-2]

        # 1 hour crossover window (last 2 candles)
        long_cross_recent = (
            (macd_2 < signal_2 and macd_1 > signal_1 and macd_1 < 0) or
            (macd_3 < signal_3 and macd_2 > signal_2 and macd_2 < 0)
        )

        short_cross_recent = (
            (macd_2 > signal_2 and macd_1 < signal_1 and macd_1 > 0) or
            (macd_3 > signal_3 and macd_2 < signal_2 and macd_2 > 0)
        )

        if trend_up and long_cross_recent:
            send_alert(f"🚀 LONG (Top50) {symbol}")

        if trend_down and short_cross_recent:
            send_alert(f"🔻 SHORT (Top50) {symbol}")

    except Exception as e:
        print(f"Error in {symbol}: {e}")

# ===== MAIN =====
symbols = get_top_50_futures()

for sym in symbols:
    check_pair(sym)
