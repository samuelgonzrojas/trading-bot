import MetaTrader5 as mt5
import pandas as pd
import time
import logging
import numpy as np
import os
import cfg.config as config

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


class GoldTrendBot:
    def __init__(self):
        self.symbol = config.bot["symbol"]  # "XAUUSD"
        self.timeframe = mt5.TIMEFRAME_H1
        self.max_open_positions = config.bot["max_positions"]
        self.lot = config.bot.get("lot", 0.1)

        self.login = config.broker["login"]
        self.password = config.broker["password"]
        self.server = config.broker["server"]

        self.initial_targets = {}

    def connect(self):
        if not mt5.initialize(
            login=self.login, password=self.password, server=self.server
        ):
            logger.error("Error al inicializar MetaTrader 5")
            raise RuntimeError("MT5 no se pudo inicializar")
        logger.info("Conexión establecida correctamente")

    def get_data(self, n=100):
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, n)
        if rates is None:
            logger.warning("No se pudieron obtener datos del símbolo.")
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
        atr = true_range.rolling(period).mean().iloc[-1]
        logger.debug(f"ATR calculado ({period}): {atr:.4f}")
        return atr

    def check_signal(self, max_bars_since_cross=3):
        logger.info("Comprobando señal de entrada...")
        df = self.get_data(n=80)
        if df is None or len(df) < 50:
            logger.warning("No hay suficientes datos para calcular señales.")
            return None

        # Cálculo de EMAs
        df["EMA9"] = df["close"].ewm(span=9).mean()
        df["EMA21"] = df["close"].ewm(span=21).mean()
        df["EMA50"] = df["close"].ewm(span=50).mean()

        curr_price = df["close"].iloc[-1]
        ema50 = df["EMA50"].iloc[-1]
        curr_fast = df["EMA9"].iloc[-1]
        curr_slow = df["EMA21"].iloc[-1]

        logger.info(
            f"Precio actual: {curr_price:.2f} | EMA9: {curr_fast:.2f} | EMA21: {curr_slow:.2f} | EMA50: {ema50:.2f}"
        )

        # Buscar último cruce
        last_cross = None
        for i in range(2, len(df)):
            fast_prev, slow_prev = df["EMA9"].iloc[-i], df["EMA21"].iloc[-i]
            fast_curr, slow_curr = df["EMA9"].iloc[-i + 1], df["EMA21"].iloc[-i + 1]

            if fast_prev <= slow_prev and fast_curr > slow_curr:
                last_cross = ("bullish", i - 1)
                break
            elif fast_prev >= slow_prev and fast_curr < slow_curr:
                last_cross = ("bearish", i - 1)
                break

        if not last_cross:
            logger.info("No se detectó ningún cruce reciente entre EMA9 y EMA21.")
            return None

        cross_type, bars_since = last_cross
        logger.debug(f"Último cruce detectado: {cross_type} hace {bars_since} velas.")

        signal = None
        if cross_type == "bullish":
            if (
                bars_since <= max_bars_since_cross
                and curr_fast > curr_slow
                and curr_price > ema50
            ):
                logger.info(
                    f"Señal de COMPRA detectada (cruce alcista hace {bars_since} velas)"
                )
                signal = "buy"
            else:
                logger.info(
                    f"Cruce alcista pero condiciones no válidas: bars={bars_since}, "
                    f"EMA9>EMA21={curr_fast > curr_slow}, precio>EMA50={curr_price > ema50}"
                )

        elif cross_type == "bearish":
            if (
                bars_since <= max_bars_since_cross
                and curr_fast < curr_slow
                and curr_price < ema50
            ):
                logger.info(
                    f"Señal de VENTA detectada (cruce bajista hace {bars_since} velas)"
                )
                signal = "sell"
            else:
                logger.info(
                    f"Cruce bajista pero condiciones no válidas: bars={bars_since}, "
                    f"EMA9<EMA21={curr_fast < curr_slow}, precio<EMA50={curr_price < ema50}"
                )

        return signal

    def place_order(self, direction):
        logger.info(f"Intentando abrir orden: {direction.upper()}")
        df = self.get_data(n=25)
        if df is None or len(df) < 15:
            logger.error("No se pueden abrir órdenes: datos insuficientes para ATR.")
            return False

        atr = self.calc_atr(df, 14)
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            logger.error("No se pudo obtener información de tick.")
            return False

        atr_sl_mult = 1.5
        atr_tp_mult = 2.0

        if direction == "buy":
            price = tick.ask
            sl = price - atr * atr_sl_mult
            tp = price + atr * atr_tp_mult
            order_type = mt5.ORDER_TYPE_BUY
        else:
            price = tick.bid
            sl = price + atr * atr_sl_mult
            tp = price - atr * atr_tp_mult
            order_type = mt5.ORDER_TYPE_SELL

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 50,
            "magic": 999001,
            "comment": "GoldTrendBot",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        logger.debug(f"Petición de orden: {request}")
        result = mt5.order_send(request)

        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            ticket = result.order
            self.initial_targets[ticket] = {"entry": price, "sl": sl, "tp": tp}
            logger.info(
                f"Orden {direction.upper()} abierta correctamente. Precio {price:.2f} | SL {sl:.2f} | TP {tp:.2f}"
            )
            return True
        else:
            logger.error(f"Error al abrir orden ({direction}): {result}")
            return False

    def count_positions(self):
        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None:
            logger.warning("No se pudieron obtener posiciones abiertas.")
            return 0
        count = len(positions)
        logger.debug(f"Posiciones abiertas en {self.symbol}: {count}")
        return count

    def update_sl(self, position, new_sl, reason):
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": position.symbol,
            "position": position.ticket,
            "sl": new_sl,
            "tp": position.tp,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"{reason}: Pos {position.ticket} | SL {new_sl:.2f}")
        else:
            logger.error(f"Error al actualizar SL ({reason}): {result}")

    def manage_positions(self):
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return

        for pos in positions:
            if pos.comment != "GoldTrendBot":
                continue

            info = self.initial_targets.get(pos.ticket)
            if not info:
                continue

            entry_price, tp = info["entry"], info["tp"]
            current_price = pos.price_current
            total_target = abs(tp - entry_price)
            current_gain = (
                (current_price - entry_price)
                if pos.type == 0
                else (entry_price - current_price)
            )
            if current_gain <= 0:
                continue

            progress = current_gain / total_target

            if progress >= 0.5 and (
                (pos.type == 0 and pos.sl < entry_price)
                or (pos.type == 1 and pos.sl > entry_price)
            ):
                self.update_sl(pos, entry_price, "SL -> BREAKEVEN")

            if progress > 0.5:
                atr = self.calc_atr(self.get_data(20), 14)
                if pos.type == 0:
                    new_sl = current_price - atr * 0.5
                    if new_sl > pos.sl:
                        self.update_sl(pos, new_sl, "TRAILING")
                else:
                    new_sl = current_price + atr * 0.5
                    if new_sl < pos.sl:
                        self.update_sl(pos, new_sl, "TRAILING")

    def run(self):
        self.connect()
        logger.info("GoldTrendBot iniciado")

        last_check_time = None

        while True:
            try:
                df = self.get_data(n=5)
                if df is None:
                    logger.warning("Datos no disponibles, esperando...")
                    time.sleep(30)
                    continue

                current_time = df["time"].iloc[-1]
                self.manage_positions()

                if current_time != last_check_time:
                    last_check_time = current_time

                    open_positions = self.count_positions()
                    logger.info(
                        f"Nueva vela detectada. Posiciones abiertas: {open_positions}"
                    )

                    if open_positions >= self.max_open_positions:
                        logger.info(
                            "Máximo de posiciones abiertas alcanzado, no se abrirán nuevas."
                        )
                        time.sleep(30)
                        continue

                    signal = self.check_signal()
                    if signal:
                        success = self.place_order(signal)
                        if not success:
                            logger.warning(
                                f"Señal '{signal}' detectada pero no se pudo abrir la orden."
                            )
                    else:
                        logger.info(
                            "Ninguna señal válida encontrada en esta comprobación."
                        )

                time.sleep(30)

            except KeyboardInterrupt:
                logger.info("Bot detenido manualmente por el usuario.")
                break
            except Exception as e:
                logger.error(f"Error inesperado: {e}", exc_info=True)
                time.sleep(60)

        logger.info("GoldTrendBot finalizado.")


if __name__ == "__main__":
    bot = GoldTrendBot()
    bot.run()
