import MetaTrader5 as mt5
import pandas as pd
import time
import logging
from datetime import datetime
import numpy as np
import cfg.config as config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("trading-bot/logs/trading_bot.log", mode="a"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class GoldPullbackBot:
    def __init__(self):
        # parámetros básicos
        self.symbol = config.bot["symbol"]
        self.timeframe = mt5.TIMEFRAME_M15  # Fijo en M15
        self.lot = config.bot["min_lot"]
        self.max_open_positions = config.bot["max_positions"]

        # conexión
        self.login = config.broker2["login"]
        self.password = config.broker2["password"]
        self.server = config.broker2["server"]

        logger.info(f"GoldPullbackBot inicializado - Hammer Strategy")

    def connect(self):
        if not mt5.initialize(
            login=self.login, password=self.password, server=self.server
        ):
            logger.error("Error al inicializar MetaTrader 5")
            raise RuntimeError("MT5 no se pudo inicializar")
        logger.info("Conexión establecida")

    def get_data(self, n=50):
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, n)
        if rates is None:
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def calc_atr(self, df, period=14):
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(period).mean().iloc[-1]

    def detect_hammer(self, df):
        """
        Detecta si la última vela es un martillo alcista.
        - Cuerpo pequeño.
        - Mecha inferior >= 2x el cuerpo.
        - Mecha superior pequeña.
        - Cierre >= apertura.
        """
        candle = df.iloc[-1]

        body = abs(candle["close"] - candle["open"])
        upper_shadow = candle["high"] - max(candle["close"], candle["open"])
        lower_shadow = min(candle["close"], candle["open"]) - candle["low"]

        if body == 0:
            return False

        is_hammer = (
            lower_shadow >= body * 2
            and upper_shadow <= body * 0.3
            and candle["close"] >= candle["open"]
        )

        if is_hammer:
            logger.info(
                f"Martillo alcista detectado | O:{candle['open']:.2f}, C:{candle['close']:.2f}, "
                f"H:{candle['high']:.2f}, L:{candle['low']:.2f}"
            )

        return is_hammer

    def is_downtrend(self, df, lookback=5):
        """
        Comprueba si ha habido una tendencia bajista en las últimas 'lookback' velas.
        Regla simple: mayoría de cierres decrecientes.
        """
        closes = df["close"].iloc[-lookback:]
        return all(closes.diff().iloc[1:] < 0)

    def check_hammer_entry(self):
        """
        Señal de COMPRA si:
        1. Hay tendencia bajista previa.
        2. Última vela es martillo alcista.
        """
        df = self.get_data(n=30)
        if df is None or len(df) < 20:
            return None

        hammer = self.detect_hammer(df)
        downtrend = self.is_downtrend(df, lookback=5)

        if hammer and downtrend:
            logger.info("SEÑAL DE COMPRA: Martillo alcista tras tendencia bajista")
            return "buy"

        return None

    def count_positions(self):
        positions = mt5.positions_get(symbol=self.symbol)
        return len(positions) if positions else 0

    def place_buy_order(self):
        """Orden con SL bajo EMA20 y TP conservador"""
        df = self.get_data(n=25)
        df["EMA20"] = df["close"].ewm(span=20).mean()

        tick = mt5.symbol_info_tick(self.symbol)
        price = tick.ask
        ema20_current = df["EMA20"].iloc[-1]
        atr = self.calc_atr(df, 14)

        # SL: Ligeramente por debajo de EMA20
        sl = ema20_current - (atr * 0.5)  # 0.5x ATR bajo EMA20

        # TP: Conservador - 2x la distancia del SL
        risk = price - sl
        tp = price + (risk * 2)  # Risk:Reward 1:2

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot,
            "type": mt5.ORDER_TYPE_BUY,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 50,
            "magic": 777777,
            "comment": "GoldPullback",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(
                f"COMPRA a {price:.2f} | SL: {sl:.2f} | TP: {tp:.2f} | Risk:Reward 1:2"
            )
            return True
        else:
            logger.error(f"Error: {result.retcode} - {result.comment}")
            return False

    def run(self):
        self.connect()
        logger.info(
            "GoldHammerBot iniciado - Buscando martillos alcistas tras tendencia bajista..."
        )

        last_check_time = None

        while True:
            try:
                df = self.get_data(n=10)
                if df is None:
                    time.sleep(10)
                    continue

                current_time = df["time"].iloc[-1]

                if current_time != last_check_time:
                    last_check_time = current_time

                    if self.count_positions() >= self.max_open_positions:
                        logger.info("Máximo de posiciones alcanzado")
                        time.sleep(60)
                        continue

                    # Chequear martillo alcista tras bajada
                    signal = self.check_hammer_entry()

                    if signal == "buy":
                        if self.place_buy_order():
                            time.sleep(300)

                time.sleep(15)

            except Exception as e:
                logger.error(f"Error: {e}")
                time.sleep(30)


if __name__ == "__main__":
    bot = GoldPullbackBot()
    bot.run()
