import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging

# ----------------------------
# CONFIGURACIÓN
# ----------------------------
SYMBOL = "XAUUSD"
TIMEFRAME = mt5.TIMEFRAME_H1
LOT = 0.1
MAGIC = 999001

# Gestión de riesgo
ATR_PERIOD = 14
SL_ATR_MULTIPLIER = 2.0
TP_ATR_MULTIPLIER = 3.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ----------------------------
# CONEXIÓN
# ----------------------------
if not mt5.initialize():
    logger.error("Error al inicializar MT5")
    quit()
logger.info("Conexión establecida con MT5")


# ----------------------------
# FUNCIONES
# ----------------------------
def get_data(n=200):
    rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, n)
    if rates is None:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def calc_atr(df, period=14):
    high_low = df["high"] - df["low"]
    high_close = np.abs(df["high"] - df["close"].shift())
    low_close = np.abs(df["low"] - df["close"].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(period).mean().iloc[-1]


def check_signal():
    df = get_data()
    if df is None or len(df) < 50:
        return None

    df["EMA9"] = df["close"].ewm(span=9).mean()
    df["EMA21"] = df["close"].ewm(span=21).mean()

    prev_fast = df["EMA9"].iloc[-2]
    prev_slow = df["EMA21"].iloc[-2]
    curr_fast = df["EMA9"].iloc[-1]
    curr_slow = df["EMA21"].iloc[-1]

    # Señales
    bullish = prev_fast <= prev_slow and curr_fast > curr_slow
    bearish = prev_fast >= prev_slow and curr_fast < curr_slow

    if bullish:
        return "buy"
    elif bearish:
        return "sell"
    return None


def count_positions():
    positions = mt5.positions_get(symbol=SYMBOL)
    return 0 if positions is None else len(positions)


def close_all_positions():
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        return
    for pos in positions:
        if pos.type == mt5.ORDER_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(SYMBOL).bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(SYMBOL).ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": SYMBOL,
            "volume": pos.volume,
            "type": order_type,
            "position": pos.ticket,
            "price": price,
            "deviation": 50,
            "magic": MAGIC,
            "comment": "Close signal",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        logger.info(f"Cerrada posición {pos.ticket} | Retcode: {result.retcode}")


def place_order(direction):
    df = get_data(100)
    atr = calc_atr(df, ATR_PERIOD)
    tick = mt5.symbol_info_tick(SYMBOL)

    if direction == "buy":
        price = tick.ask
        sl = price - atr * SL_ATR_MULTIPLIER
        tp = price + atr * TP_ATR_MULTIPLIER
        order_type = mt5.ORDER_TYPE_BUY
    else:
        price = tick.bid
        sl = price + atr * SL_ATR_MULTIPLIER
        tp = price - atr * TP_ATR_MULTIPLIER
        order_type = mt5.ORDER_TYPE_SELL

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": LOT,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 50,
        "magic": MAGIC,
        "comment": f"EMA9/21 {direction}",
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(f"{direction.upper()} {price:.2f} | SL {sl:.2f} | TP {tp:.2f}")
        return True
    else:
        logger.error(f"Error al abrir: {result.retcode} - {result.comment}")
        return False


# ----------------------------
# LOOP PRINCIPAL
# ----------------------------
logger.info("Bot EMA9/21 iniciado (XAUUSD, H1, ATR SL/TP)")

last_time = None

while True:
    try:
        df = get_data(5)
        if df is None:
            time.sleep(30)
            continue

        current_time = df["time"].iloc[-1]
        if current_time != last_time:
            last_time = current_time

            signal = check_signal()
            if signal and count_positions() == 0:
                place_order(signal)

            elif signal and count_positions() > 0:
                # cierre inverso
                close_all_positions()
                place_order(signal)

        time.sleep(10)

    except KeyboardInterrupt:
        logger.info("Bot detenido por usuario")
        break
    except Exception as e:
        logger.error(f"Error: {e}")
        time.sleep(30)

mt5.shutdown()
