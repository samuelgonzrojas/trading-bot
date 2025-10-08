import MetaTrader5 as mt5
import pandas as pd
import time
import logging
from datetime import datetime
import numpy as np
import cfg.config as config

# ----------------------------
# Configuración de logging
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("trading-bot/logs/trading_bot.log", mode="a"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

CSV_FILE = "trading-bot/data/trades.csv"


class FibonacciBot:
    def __init__(self):
        self.account_balance = 0
        self.start_equity = 0

        # parámetros de ajuste
        self.symbol = config.bot["symbol"]
        self.timeframe = getattr(mt5, f"TIMEFRAME_{config.bot['timeframe']}")
        self.risk = config.bot["risk"]
        self.max_open_positions = config.bot["max_positions"]
        self.lot = config.bot["min_lot"]
        self.tp_atr_mult = config.bot["tp_atr_mult"]
        self.sl_atr_mult = config.bot["sl_atr_mult"]
        self.trailing_atr_mult = config.bot["trailing_atr_mult"]
        self.atr_period = config.bot["atr_period"]
        self.session_hours = config.bot["session_hours"]

        # conexión
        self.name = config.broker["name"]
        self.login = config.broker["login"]
        self.password = config.broker["password"]
        self.server = config.broker["server"]

        # filtros
        self.conditions = 0
        self.max_conditions = config.bot["max_conditions"]

        logger.info(f"FibonacciBot inicializado para {self.symbol}")

    def connect(self, login=None, password=None, server=None):
        login = login or self.login
        password = password or self.password
        server = server or self.server

        if not mt5.initialize(login=login, password=password, server=server):
            logger.error("Error al inicializar MetaTrader 5")
            raise RuntimeError("MT5 no se pudo inicializar")
        logger.info(f"Conexión a MetaTrader 5 establecida. Cuenta: {login}")

        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            raise RuntimeError(f"Símbolo {self.symbol} no disponible")

        if not symbol_info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL:
            logger.warning(f"Símbolo {self.symbol} con restricciones de trading")

        logger.info(f"Spread actual: {symbol_info.spread} puntos")

    def get_data(self, n=500, timeframe=None):
        tf = timeframe or self.timeframe
        rates = mt5.copy_rates_from_pos(self.symbol, tf, 0, n)
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def calc_atr(self, df, period=14):
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(period).mean()
        return atr.iloc[-1]

    def check_fibonacci_filter(self):
        df = self.get_data(n=50)
        swing_period = 5
        df["is_swing_high"] = False
        df["is_swing_low"] = False

        for i in range(swing_period, len(df) - swing_period):
            if (
                df.iloc[i]["high"]
                == df.iloc[i - swing_period : i + swing_period + 1]["high"].max()
            ):
                df.iloc[i, df.columns.get_loc("is_swing_high")] = True
            if (
                df.iloc[i]["low"]
                == df.iloc[i - swing_period : i + swing_period + 1]["low"].min()
            ):
                df.iloc[i, df.columns.get_loc("is_swing_low")] = True

        recent_data = df.iloc[-30:]
        swing_highs = recent_data[recent_data["is_swing_high"]]
        swing_lows = recent_data[recent_data["is_swing_low"]]

        if len(swing_highs) == 0 or len(swing_lows) == 0:
            return None

        swing_high = swing_highs["high"].max()
        swing_low = swing_lows["low"].min()
        swing_range = swing_high - swing_low
        atr = self.calc_atr(df, self.atr_period)

        if swing_range < atr * 2:
            return None

        levels = {
            "23.6": swing_high - swing_range * 0.236,
            "38.2": swing_high - swing_range * 0.382,
            "50.0": swing_high - swing_range * 0.5,
            "61.8": swing_high - swing_range * 0.618,
            "78.6": swing_high - swing_range * 0.786,
        }

        last_close = df["close"].iloc[-1]
        tolerance = atr * 1.0  # MÁS AMPLIA

        # Soporte (compra)
        for level_name in ["38.2", "50.0"]:
            if (
                abs(last_close - levels[level_name]) < tolerance
                and last_close > swing_low * 1.01
            ):
                return "buy"

        # Resistencia (venta)
        for level_name in ["61.8", "78.6"]:
            if (
                abs(last_close - levels[level_name]) < tolerance
                and last_close < swing_high * 0.99
            ):
                return "sell"

        return None

    def check_trend_filter(self):
        # Tendencia en 1H
        df_h1 = self.get_data(n=200, timeframe=mt5.TIMEFRAME_H1)
        df_h1["EMA20"] = df_h1["close"].ewm(span=20).mean()
        trend_h1 = (
            "buy" if df_h1["close"].iloc[-1] > df_h1["EMA20"].iloc[-1] else "sell"
        )

        # Tendencia en 4H
        df_h4 = self.get_data(n=200, timeframe=mt5.TIMEFRAME_H4)
        df_h4["EMA20"] = df_h4["close"].ewm(span=20).mean()
        trend_h4 = (
            "buy" if df_h4["close"].iloc[-1] > df_h4["EMA20"].iloc[-1] else "sell"
        )

        if trend_h1 == trend_h4:
            return trend_h1
        return None

    def check_momentum_filter(self):
        df = self.get_data(n=30)

        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        last_rsi = rsi.iloc[-1]

        # Última vela como patrón simple
        last_candle = df.iloc[-2]  # vela cerrada
        bullish = last_candle["close"] > last_candle["open"]
        bearish = last_candle["close"] < last_candle["open"]

        if last_rsi < 35 and bullish:
            return "buy"
        elif last_rsi > 65 and bearish:
            return "sell"
        return None

    def count_open_positions(self):
        positions = mt5.positions_get(symbol=self.symbol)
        return len(positions) if positions else 0

    def place_order(self, action, lot, atr):
        tick = mt5.symbol_info_tick(self.symbol)
        price = tick.ask if action == "buy" else tick.bid

        sl_distance = atr * self.sl_atr_mult
        tp_distance = atr * self.tp_atr_mult

        sl = price - sl_distance if action == "buy" else price + sl_distance
        tp = price + tp_distance if action == "buy" else price - tp_distance

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_BUY if action == "buy" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 50,
            "magic": 123456,
            "comment": "FibonacciBot",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(
                f"{action.upper()} ejecutada a {price:.2f} SL:{sl:.2f} TP:{tp:.2f}"
            )
        else:
            logger.error(
                f"Error {action.upper()} Retcode={result.retcode}, Comment={result.comment}"
            )
        return result

    def apply_trailing_stop(self, atr_mult=1.0):
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return

        atr = self.calc_atr(self.get_data(n=100), self.atr_period)
        for pos in positions:
            tick = mt5.symbol_info_tick(self.symbol)
            price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
            new_sl = (
                price - atr * atr_mult
                if pos.type == mt5.POSITION_TYPE_BUY
                else price + atr * atr_mult
            )

            if (pos.type == mt5.POSITION_TYPE_BUY and new_sl > pos.sl) or (
                pos.type == mt5.POSITION_TYPE_SELL and new_sl < pos.sl
            ):
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "symbol": self.symbol,
                    "position": pos.ticket,
                    "sl": new_sl,
                    "tp": pos.tp,
                }
                mt5.order_send(request)
                logger.info(
                    f"Trailing Stop actualizado: Pos {pos.ticket} -> SL {new_sl:.2f}"
                )

    def in_session_hours(self):
        now_hour = datetime.now().hour
        return any(start <= now_hour < end for start, end in self.session_hours)

    def run(self):
        self.connect()
        account_info = mt5.account_info()
        self.account_balance = account_info.balance
        self.start_equity = account_info.equity
        logger.info(
            f"Bot iniciado. Balance: {self.account_balance:.2f}, Equity: {self.start_equity:.2f}"
        )

        last_processed_time = None

        while True:
            if not self.in_session_hours():
                logger.info("Fuera de horario de sesión. Bot en pausa.")
                time.sleep(60)
                continue

            df = self.get_data(n=20)
            last_closed_time = df["time"].iloc[-2]

            if last_closed_time != last_processed_time:
                last_processed_time = last_closed_time

                atr = self.calc_atr(df, self.atr_period)

                cond_fib = self.check_fibonacci_filter()
                cond_trend = self.check_trend_filter()
                cond_momentum = self.check_momentum_filter()

                # Contar cuántos filtros han dado señal (buy/sell, no None)
                signals = [cond_fib, cond_trend, cond_momentum]
                signals_filtered = [s for s in signals if s in ("buy", "sell")]
                self.conditions = len(signals_filtered)

                # Determinar si hay consenso (al menos dos señales iguales)
                signal = None
                if self.conditions >= 2:
                    if signals_filtered.count("buy") >= 2:
                        signal = "buy"
                    elif signals_filtered.count("sell") >= 2:
                        signal = "sell"

                # Contar cuántas condiciones se cumplen
                print(
                    f"cond_fib: {cond_fib}, cond_trend: {cond_trend}, cond_momentum: {cond_momentum}"
                )

                if signal and self.conditions >= self.max_conditions:
                    if self.count_open_positions() < self.max_open_positions:
                        lot = self.lot
                        self.place_order(signal, lot, atr)
                    else:
                        logger.info("Máximo de posiciones abiertas alcanzado.")
                else:
                    logger.info(
                        f"No se cumplen suficientes condiciones (cumple {self.conditions}/3)"
                    )

            # trailing stop
            self.apply_trailing_stop(self.trailing_atr_mult)
            time.sleep(5)


if __name__ == "__main__":
    bot = FibonacciBot()
    bot.run()
