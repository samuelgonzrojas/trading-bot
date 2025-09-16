import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime
import logging

# ================= CONFIGURACIÓN ==================
SYMBOL = "EURUSD"  # Par de divisas
TIMEFRAME = mt5.TIMEFRAME_M15  # Marco temporal
LOT = 0.1  # Tamaño de lote
FAST = 9  # Periodo media rápida
SLOW = 21  # Periodo media lenta
MAGIC = 123456  # Identificador de la estrategia

# Configuración de logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

# ================ CONEXIÓN MT5 ====================
if not mt5.initialize():
    logging.error("❌ No se pudo inicializar MetaTrader5")
    quit()

account_info = mt5.account_info()
if account_info is None:
    logging.error("❌ No se pudo obtener la cuenta")
    mt5.shutdown()
    quit()
else:
    logging.info(
        f"✅ Conectado a cuenta: {account_info.login}, Balance: {account_info.balance}"
    )


# ============== FUNCIONES =========================
def get_data(symbol, timeframe, n=200):
    """Obtiene datos de velas en un DataFrame"""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n)
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def get_ma_signals(df):
    """Genera señales basadas en cruce de medias"""
    df["ma_fast"] = df["close"].rolling(FAST).mean()
    df["ma_slow"] = df["close"].rolling(SLOW).mean()

    if (
        df["ma_fast"].iloc[-2] < df["ma_slow"].iloc[-2]
        and df["ma_fast"].iloc[-1] > df["ma_slow"].iloc[-1]
    ):
        return "BUY"
    elif (
        df["ma_fast"].iloc[-2] > df["ma_slow"].iloc[-2]
        and df["ma_fast"].iloc[-1] < df["ma_slow"].iloc[-1]
    ):
        return "SELL"
    return None


def send_order(symbol, order_type, lot=LOT):
    """Envía una orden al mercado"""
    price = (
        mt5.symbol_info_tick(symbol).ask
        if order_type == "BUY"
        else mt5.symbol_info_tick(symbol).bid
    )
    order_type_mt5 = mt5.ORDER_TYPE_BUY if order_type == "BUY" else mt5.ORDER_TYPE_SELL

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type_mt5,
        "price": price,
        "sl": 0.0,
        "tp": 0.0,
        "deviation": 20,
        "magic": MAGIC,
        "comment": "Cruce de medias",
        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"❌ Error en orden {order_type}: {result.retcode}")
    else:
        logging.info(f"✅ Orden {order_type} ejecutada al precio {price}")


# =============== LOOP PRINCIPAL ====================
logging.info("🚀 Iniciando bot de cruce de medias...")

while True:
    df = get_data(SYMBOL, TIMEFRAME, 200)
    signal = get_ma_signals(df)

    if signal:
        logging.info(f"📊 Señal detectada: {signal}")
        send_order(SYMBOL, signal)

    time.sleep(60)  # Espera un minuto antes de revisar otra vez
