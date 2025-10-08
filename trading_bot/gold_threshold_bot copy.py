import MetaTrader5 as mt5
import pandas as pd
import time
import logging
import os
import numpy as np
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


class ThresholdMomentumBot:
    def __init__(self):
        self.symbol = config.bot["symbol"]
        self.lot = config.bot["lot"]

        # Parámetros (ajusta en config.bot)
        self.threshold = config.bot.get("threshold", 0.20)  # unidad de precio
        self.stop_loss = config.bot.get("stop_loss", 0.10)  # stop adverso desde entry
        self.tp_mult = config.bot.get("tp_mult", 3.0)  # TP = threshold * tp_mult
        self.trailing_start = config.bot.get(
            "trailing_start", 1.0
        )  # start trailing after X (price units)
        self.trailing_buffer = config.bot.get(
            "trailing_buffer", 0.2
        )  # distancia del SL al price al trail
        self.use_atr = config.bot.get(
            "use_atr", False
        )  # si True, recalcula thresholds con ATR
        self.atr_mult_for_threshold = config.bot.get("atr_mult_for_threshold", 0.5)

        self.max_open_positions = config.bot.get("max_positions", 1)

        self.login = config.broker["login"]
        self.password = config.broker["password"]
        self.server = config.broker["server"]

        # Estado
        self.ref_price = None  # precio desde el que medimos el primer movimiento
        self.entry_price = None
        self.position_type = None  # "buy" o "sell"
        self.open_ticket = None

        logger.info(f"ThresholdMomentumBot inicializado - {self.symbol}")

    def connect(self):
        if not mt5.initialize(
            login=self.login, password=self.password, server=self.server
        ):
            logger.error("Error al inicializar MetaTrader 5")
            raise RuntimeError("MT5 no se pudo inicializar")
        logger.info("Conexión establecida")

    def get_price(self):
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            raise RuntimeError("No tick info")
        return tick.bid, tick.ask

    def get_data(self, n=50):
        rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M1, 0, n)
        if rates is None:
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def calc_atr(self, period=14):
        df = self.get_data(n=period + 5)
        if df is None or len(df) < period:
            return None
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(period).mean().iloc[-1]

    def open_order(self, order_type):
        bid, ask = self.get_price()
        price = ask if order_type == "buy" else bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot,
            "type": mt5.ORDER_TYPE_BUY if order_type == "buy" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "deviation": 50,
            "magic": 123456,
            "comment": "ThresholdMomentum",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            self.entry_price = price
            self.position_type = order_type
            # Si la respuesta tiene ticket, guardarlo
            try:
                self.open_ticket = result.order if hasattr(result, "order") else None
            except Exception:
                self.open_ticket = None
            logger.info(f"{order_type.upper()} abierto a {price:.5f}")
            # Reset ref_price para evitar reentrada inmediata
            self.ref_price = None
            return True
        else:
            logger.error(
                f"Error al abrir {order_type}: {result.retcode} - {getattr(result, 'comment', '')}"
            )
            return False

    def close_all_positions(self, reason=""):
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return False
        ok = True
        for pos in positions:
            # cerrar con la orden contraria
            close_type = (
                mt5.ORDER_TYPE_SELL
                if pos.type == mt5.ORDER_TYPE_BUY
                else mt5.ORDER_TYPE_BUY
            )
            bid, ask = self.get_price()
            price = bid if close_type == mt5.ORDER_TYPE_SELL else ask
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": pos.volume,
                "type": close_type,
                "position": pos.ticket,
                "price": price,
                "deviation": 50,
                "magic": 123456,
                "comment": f"Close-{reason}",
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(close_request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"Cerrada pos {pos.ticket} por {reason} a {price:.5f}")
            else:
                ok = False
                logger.error(f"Error cerrando pos {pos.ticket}: {result.retcode}")
        # limpiar estado local si cerradas
        if ok:
            self.entry_price = None
            self.position_type = None
            self.open_ticket = None
        return ok

    def update_sl(self, position_ticket, new_sl):
        # Actualizar SL con TRADE_ACTION_SLTP
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": self.symbol,
            "position": position_ticket,
            "sl": new_sl,
            "tp": 0.0,
        }
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"SL actualizado pos {position_ticket} -> {new_sl:.5f}")
            return True
        else:
            logger.error(f"Error actualizando SL: {result.retcode}")
            return False

    def count_open_positions(self):
        positions = mt5.positions_get(symbol=self.symbol)
        return len(positions) if positions is not None else 0

    def run(self):
        self.connect()
        logger.info("ThresholdMomentumBot iniciado")
        consecutive_errors = 0

        # Si usas ATR para ajustar threshold, calcula una vez al iniciar y periódicamente
        atr = None
        if self.use_atr:
            atr = self.calc_atr(14)
            if atr:
                logger.info(f"ATR(14) inicial: {atr:.5f}")

        while True:
            try:
                bid, ask = self.get_price()
                mid_price = (bid + ask) / 2.0

                # recalcula threshold dinámico si usas ATR
                effective_threshold = self.threshold
                if self.use_atr and atr:
                    effective_threshold = atr * self.atr_mult_for_threshold

                # Si no hay ref_price definimos uno y esperamos un pequeño movimiento
                if self.ref_price is None and self.entry_price is None:
                    self.ref_price = mid_price
                    time.sleep(0.3)
                    continue

                # Si no hay posición abierta, miramos si el movimiento desde ref supera threshold
                if self.count_open_positions() == 0 and self.entry_price is None:
                    move_from_ref = mid_price - self.ref_price

                    if move_from_ref >= effective_threshold:
                        # Abrir BUY
                        self.open_order("buy")
                        # opcional: definir un TP (por ejemplo)
                        # tp_price = self.entry_price + effective_threshold * self.tp_mult
                    elif move_from_ref <= -effective_threshold:
                        # Abrir SELL
                        self.open_order("sell")

                    # si no abrimos, dejamos ref_price y seguimos
                    time.sleep(0.3)
                    continue

                # Si hay posición abierta, gestionarla
                if self.entry_price is not None and self.position_type is not None:
                    # Para calcular movimiento real a efectos de cierre:
                    # - si estamos long: precio de cierre potencial = bid (porque cerraríamos vendiendo)
                    # - si short: precio de cierre potencial = ask (cerraríamos comprando)
                    close_price = bid if self.position_type == "buy" else ask

                    if self.position_type == "buy":
                        move_from_entry = close_price - self.entry_price
                        # Adverse: retroceso mayor que stop_loss
                        if move_from_entry <= -self.stop_loss:
                            logger.info(
                                f"Retroceso adverso {move_from_entry:.5f} <= -{self.stop_loss:.5f} -> cerrar"
                            )
                            self.close_all_positions(reason="AdverseStop")
                            continue

                        # Si ha avanzado lo suficiente para empezar a trail
                        if move_from_entry >= self.trailing_start:
                            # calcula nuevo SL (proteger trailing_buffer desde precio actual)
                            new_sl = close_price - self.trailing_buffer
                            # obtener posiciones para ver SL actual y ticket
                            positions = mt5.positions_get(symbol=self.symbol)
                            if positions:
                                for pos in positions:
                                    if (
                                        pos.comment == "ThresholdMomentum"
                                        or pos.ticket == self.open_ticket
                                    ):
                                        # actualiza solo si new_sl > pos.sl (mejor para buy)
                                        if new_sl > pos.sl:
                                            self.update_sl(pos.ticket, new_sl)

                        # Opcional: cerrar si alcanza TP rígido
                        tp_price = self.entry_price + effective_threshold * self.tp_mult
                        if close_price >= tp_price:
                            logger.info(
                                f"TP alcanzado {close_price:.5f} >= {tp_price:.5f} -> cerrar"
                            )
                            self.close_all_positions(reason="TP")
                            continue

                    else:  # posición sell
                        move_from_entry = self.entry_price - close_price
                        if move_from_entry <= -self.stop_loss:
                            logger.info(
                                f"Retroceso adverso (sell) {move_from_entry:.5f} <= -{self.stop_loss:.5f} -> cerrar"
                            )
                            self.close_all_positions(reason="AdverseStop")
                            continue

                        if move_from_entry >= self.trailing_start:
                            new_sl = close_price + self.trailing_buffer
                            positions = mt5.positions_get(symbol=self.symbol)
                            if positions:
                                for pos in positions:
                                    if (
                                        pos.comment == "ThresholdMomentum"
                                        or pos.ticket == self.open_ticket
                                    ):
                                        # para sell, new_sl < pos.sl (pos.sl is lower number) -> actualizar si es mejor
                                        if pos.sl == 0.0 or new_sl < pos.sl:
                                            self.update_sl(pos.ticket, new_sl)

                        tp_price = self.entry_price - effective_threshold * self.tp_mult
                        if close_price <= tp_price:
                            logger.info(
                                f"TP alcanzado (sell) {close_price:.5f} <= {tp_price:.5f} -> cerrar"
                            )
                            self.close_all_positions(reason="TP")
                            continue

                time.sleep(0.5)

            except KeyboardInterrupt:
                logger.info("Bot detenido por usuario")
                break
            except Exception as e:
                logger.error(f"Error inesperado: {e}")
                consecutive_errors += 1
                time.sleep(1)
                if consecutive_errors > 10:
                    # recalcula ATR por si lo usas
                    if self.use_atr:
                        atr = self.calc_atr(14)
                        logger.info(f"Recalculado ATR: {atr}")
                    consecutive_errors = 0


if __name__ == "__main__":
    bot = ThresholdMomentumBot()
    bot.run()
