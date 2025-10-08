# ==============================
# Configuración del broker
# ==============================
broker = {
    "name": "Bot Santiago",
    "login": 5040181463,
    "password": "YrFx@k2c",
    "server": "MetaQuotes-Demo",
}

broker2 = {
    "name": "Bot Rodrigo",
    "login": 96792422,
    "password": "N@MaX6Rt",
    "server": "MetaQuotes-Demo",
}

# ==============================
# Configuración del bot
# ==============================
bot = {
    "symbol": "XAUUSD",  # símbolo a operar
    "timeframe": "H1",  # marco temporal
    "atr_period": 14,  # período para ATR
    "tp_atr_mult": 3.0,  # multiplicador para take profit
    "sl_atr_mult": 2.0,  # multiplicador para stop loss
    "lot": 0.05,  # tamaño de lote
    "max_positions": 1,  # máximo de posiciones abiertas
    "near_ema_pct": 0.0015,  # porcentaje para considerar "cerca" de la EMA20 (0.15%)
    "max_distance_pct": 0.003,  # distancia máxima desde EMA20 para entrada (0.3%)
}

bot_eurusd = {
    "symbol": "EURUSD",  # símbolo a operar
    "timeframe": "H1",  # marco temporal
    "atr_period": 14,  # período para ATR
    "tp_atr_mult": 3.0,  # multiplicador para take profit
    "sl_atr_mult": 2.0,  # multiplicador para stop loss
    "lot": 0.05,  # tamaño de lote
    "max_positions": 1,  # máximo de posiciones abiertas
    "near_ema_pct": 0.0015,  # porcentaje para considerar "cerca" de la EMA20 (0.15%)
    "max_distance_pct": 0.003,  # distancia máxima desde EMA20 para entrada (0.3%)
}

bitcoin_bot = {
    "symbol": "BTCUSDT",  # símbolo a operar
    "timeframe": "5m",  # marco temporal
    "lot": 0.01,  # tamaño de lote
    "max_positions": 1,  # máximo de posiciones abiertas
}

binance_api = {
    "api_key": "d69a5faa37edaccef36f054d0aedd491e8d1af1995132d2306620c7ce15a3773",
    "api_secret": "c8bd50a0243d7cff9b3fc6c0fdee80f94edc3ef6d10d078dff3602aa84644925",
    "testnet": True,
}
