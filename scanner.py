import ccxt
import pandas as pd
import requests
import os

# ===== TELEGRAM =====
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

# ===== OKX FUTURES =====
exchange = ccxt.okx({
    'enableRateLimit': True,
    'options': {
        'defaultType': 'swap'   # perpetual futures
    }
})

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": message})

# ===== TOP 50 USDT SWAPS BY VOLUME =====
def get_top_50():
    markets = exchange.load_markets()
    tickers = exchange.fetch_tickers()
    pairs = []

    for symbol in markets:
        if "USDT" in symbol and markets[symbol]['active']:
            if symbol in tickers:
                volume = tickers[symbol].get('quoteVolume', 0)
                pairs.append((symbol, volume))

    pairs.sort(key=lambda x: x[1], reverse=True)
    return [p[0] for p in pairs[:50]]

# ===== STRATEGY =====
def check_pair(symbol):
    try:
        # 1H EMA
        ohlc_1h = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=250)
        df1h = pd.DataFrame(ohlc_1h, columns=['t','o','h','l','c','v'])
        df1h['ema200'] = df1h['c'].ewm(span=200).mean()

        trend_up = df1h['c'].iloc[-2] > df1h['ema200'].iloc[-2]
        trend_down = df1h['c'].iloc[-2] < df1h['ema200'].iloc[-2]

        # 30M MACD
        ohlc_30 = exchange.fetch_ohlcv(symbol, timeframe='30m', limit=100)
        df30 = pd.DataFrame(ohlc_30, columns=['t','o','h','l','c','v'])

        df30['macd'] = df30['c'].ewm(span=12).mean() - df30['c'].ewm(span=26).mean()
        df30['signal'] = df30['macd'].ewm(span=9).mean()

        macd_3 = df30['macd'].iloc[-4]
        macd_2 = df30['macd'].iloc[-3]
        macd_1 = df30['macd'].iloc[-2]

        signal_3 = df30['signal'].iloc[-4]
        signal_2 = df30['signal'].iloc[-3]
        signal_1 = df30['signal'].iloc[-2]

        long_recent = (
            (macd_2 < signal_2 and macd_1 > signal_1 and macd_1 < 0) or
            (macd_3 < signal_3 and macd_2 > signal_2 and macd_2 < 0)
        )

        short_recent = (
            (macd_2 > signal_2 and macd_1 < signal_1 and macd_1 > 0) or
            (macd_3 > signal_3 and macd_2 < signal_2 and macd_2 > 0)
        )

        if trend_up and long_recent:
            send_alert(f"🚀 LONG (OKX) {symbol}")

        if trend_down and short_recent:
            send_alert(f"🔻 SHORT (OKX) {symbol}")

    except Exception as e:
        print(f"Error in {symbol}: {e}")

# ===== MAIN =====
symbols = get_top_50()

for s in symbols:
    check_pair(s)
