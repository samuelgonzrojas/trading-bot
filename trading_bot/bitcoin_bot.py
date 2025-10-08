import pandas as pd
import time
import logging
import numpy as np
import os
from binance.client import Client
import cfg.config as config

# =============================
# LOGGING
# =============================
filename = os.path.basename(__file__).replace(".py", "")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"trading_bot/logs/{filename}.log", mode="a"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class BTCFuturesBot:
    def __init__(self):
        self.symbol = config.bitcoin_bot["symbol"]  # "BTCUSDT"
        self.timeframe = config.bitcoin_bot["timeframe"]  # "1m", "5m", etc
        self.lot = config.bitcoin_bot["lot"]  # cantidad a operar
        self.max_open_positions = config.bitcoin_bot["max_positions"]

        # Cliente Binance Futures Testnet
        self.client = Client(
            config.binance_api["api_key"],
            config.binance_api["api_secret"],
            testnet=True,
        )
        # Override URL para Futures Testnet
        self.client.FUTURES_URL = "https://testnet.binancefuture.com/fapi"

        self.in_position = False
        logger.info("BTCFuturesBot inicializado - Estrategia EMA9/21 + EMA5/13")

    # =============================
    # DATA
    # =============================
    def get_data(self, n=100):
        klines = self.client.futures_klines(
            symbol=self.symbol, interval=self.timeframe, limit=n
        )
        df = pd.DataFrame(
            klines,
            columns=[
                "time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "qav",
                "num_trades",
                "taker_base_vol",
                "taker_quote_vol",
                "ignore",
            ],
        )
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df["close"] = df["close"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        return df

    def calc_atr(self, df, period=14):
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(period).mean().iloc[-1]

    # =============================
    # ESTRATEGIA
    # =============================
    def check_ma_crossover_entry(self):
        df = self.get_data(n=50)
        if len(df) < 30:
            return None

        df["EMA9"] = df["close"].ewm(span=9).mean()
        df["EMA21"] = df["close"].ewm(span=21).mean()

        prev_fast = df["EMA9"].iloc[-2]
        prev_slow = df["EMA21"].iloc[-2]
        curr_fast = df["EMA9"].iloc[-1]
        curr_slow = df["EMA21"].iloc[-1]

        print(f"Prev EMA9: {prev_fast:.2f}, Prev EMA21: {prev_slow:.2f}")
        print(f"Curr EMA9: {curr_fast:.2f}, Curr EMA21: {curr_slow:.2f}")

        bullish_crossover = prev_fast <= prev_slow and curr_fast > curr_slow

        if bullish_crossover:
            logger.info(
                f"CROSSOVER ENTRY: EMA9 {curr_fast:.2f} > EMA21 {curr_slow:.2f}"
            )
            return "buy"
        return None

    def check_ma_crossover_exit(self):
        df = self.get_data(n=30)
        if len(df) < 20:
            return False

        df["EMA5"] = df["close"].ewm(span=5).mean()
        df["EMA13"] = df["close"].ewm(span=13).mean()

        prev_fast = df["EMA5"].iloc[-2]
        prev_slow = df["EMA13"].iloc[-2]
        curr_fast = df["EMA5"].iloc[-1]
        curr_slow = df["EMA13"].iloc[-1]

        return prev_fast >= prev_slow and curr_fast < curr_slow

    def detect_early_weakness(self):
        df = self.get_data(n=15)
        if len(df) < 10:
            return False

        df["EMA8"] = df["close"].ewm(span=8).mean()

        last_close = df["close"].iloc[-1]
        prev_close = df["close"].iloc[-2]
        last_ema8 = df["EMA8"].iloc[-1]
        prev_ema8 = df["EMA8"].iloc[-2]

        two_closes_below = (last_close < last_ema8) and (prev_close < prev_ema8)
        ema8_falling = last_ema8 < prev_ema8

        return two_closes_below and ema8_falling

    # =============================
    # ÓRDENES
    # =============================
    def place_buy_order(self):
        df = self.get_data(n=25)
        atr = self.calc_atr(df, 14)

        ticker = self.client.futures_symbol_ticker(symbol=self.symbol)
        price = float(ticker["price"])

        sl = price - atr * 2
        tp = price + atr * 3

        order = self.client.futures_create_order(
            symbol=self.symbol, side="BUY", type="MARKET", quantity=self.lot
        )

        logger.info(f"COMPRA {price:.2f} | SL {sl:.2f} | TP {tp:.2f} | ATR {atr:.2f}")
        return order

    def place_sell_order(self):
        ticker = self.client.futures_symbol_ticker(symbol=self.symbol)
        price = float(ticker["price"])

        order = self.client.futures_create_order(
            symbol=self.symbol,
            side="SELL",
            type="MARKET",
            quantity=self.lot,
        )

        logger.info(f"VENTA {price:.2f} | Cerrando posición")
        return order

    # =============================
    # LOOP PRINCIPAL
    # =============================
    def run(self):
        last_check_time = None
        while True:
            try:
                df = self.get_data(n=5)
                current_time = df["time"].iloc[-1]

                if current_time != last_check_time:
                    last_check_time = current_time

                    # Entrada
                    signal = self.check_ma_crossover_entry()
                    if signal == "buy" and not self.in_position:
                        self.place_buy_order()
                        self.in_position = True
                        logger.info("Esperando 5 minutos antes de nueva entrada...")
                        time.sleep(300)

                # Salida
                if self.in_position and (
                    self.check_ma_crossover_exit() or self.detect_early_weakness()
                ):
                    self.place_sell_order()
                    self.in_position = False
                    logger.info("Posición cerrada")
                    time.sleep(60)

                time.sleep(15)

            except KeyboardInterrupt:
                logger.info("Bot detenido por usuario")
                break
            except Exception as e:
                logger.error(f"Error inesperado: {e}")
                time.sleep(30)


if __name__ == "__main__":
    bot = BTCFuturesBot()
    bot.run()
