import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime
import yaml

config = yaml.safe_load(open("trading-bot/config.yaml", "r"))


class ScalpingBot:
    def __init__(self, symbol="XAUUSD", timeframe=mt5.TIMEFRAME_M1, risk=0.01):
        self.symbol = symbol
        self.timeframe = timeframe
        self.risk = risk
        self.daily_profit_target = 0.005  # +0.5% diario
        self.max_daily_loss = 0.01  # -1% diario
        self.account_balance = 0
        self.start_equity = 0
        self.max_open_positions = 3

        # Configuración de scalping
        self.take_profit_pips = 50  # TP inicial
        self.stop_loss_pips = 25  # SL inicial
        self.min_profit_close = 5.0  # $ cerrar manualmente si excede este profit
        self.break_even_trigger = 3.0  # $ cuando se alcanza, mover SL a entrada

        self.name = config["broker"]["name"]
        self.login = config["broker"]["login"]
        self.password = config["broker"]["password"]
        self.server = config["broker"]["server"]

        print(f"ScalpingBot inicializado para {self.symbol}")

    def connect(self):
        if not mt5.initialize(
            login=self.login, password=self.password, server=self.server
        ):
            raise RuntimeError("MT5 no se pudo inicializar")
        print("Conectado a MetaTrader 5")

    def get_data(self, n=200):
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, n)
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def check_signal(self, df):
        # Cruce de medias rápidas
        df["ema_fast"] = df["close"].ewm(span=9).mean()
        df["ema_slow"] = df["close"].ewm(span=21).mean()

        if (
            df["ema_fast"].iloc[-2] < df["ema_slow"].iloc[-2]
            and df["ema_fast"].iloc[-1] > df["ema_slow"].iloc[-1]
        ):
            print(f"[{datetime.now()}] Señal COMPRA detectada (cruce alcista)")
            return "buy"

        if (
            df["ema_fast"].iloc[-2] > df["ema_slow"].iloc[-2]
            and df["ema_fast"].iloc[-1] < df["ema_slow"].iloc[-1]
        ):
            print(f"[{datetime.now()}] Señal VENTA detectada (cruce bajista)")
            return "sell"

        return None

    def count_open_positions(self):
        positions = mt5.positions_get(symbol=self.symbol)
        return len(positions) if positions else 0

    def place_order(self, action, lot):
        tick = mt5.symbol_info_tick(self.symbol)
        price = tick.ask if action == "buy" else tick.bid
        point = mt5.symbol_info(self.symbol).point

        sl = (
            price - self.stop_loss_pips * point
            if action == "buy"
            else price + self.stop_loss_pips * point
        )
        tp = (
            price + self.take_profit_pips * point
            if action == "buy"
            else price - self.take_profit_pips * point
        )

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_BUY if action == "buy" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 50,
            "magic": 987654,
            "comment": "ScalpingBot",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        print(
            f"[{datetime.now()}] Orden {action.upper()} enviada. Retcode={result.retcode}"
        )

    def close_all_positions(self):
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return
        for pos in positions:
            lot = pos.volume
            price = (
                mt5.symbol_info_tick(self.symbol).bid
                if pos.type == mt5.POSITION_TYPE_BUY
                else mt5.symbol_info_tick(self.symbol).ask
            )
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": lot,
                "type": (
                    mt5.ORDER_TYPE_SELL
                    if pos.type == mt5.POSITION_TYPE_BUY
                    else mt5.ORDER_TYPE_BUY
                ),
                "position": pos.ticket,
                "price": price,
                "deviation": 50,
                "magic": 987654,
                "comment": "ScalpingBot cierre forzado",
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            mt5.order_send(request)
            print(
                f"[{datetime.now()}] Posición {pos.ticket} cerrada por cierre forzado"
            )

    def check_individual_profits(self):
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return

        for pos in positions:
            # Cerrar si supera el profit en $
            if pos.profit >= self.min_profit_close:
                price = (
                    mt5.symbol_info_tick(self.symbol).bid
                    if pos.type == mt5.POSITION_TYPE_BUY
                    else mt5.symbol_info_tick(self.symbol).ask
                )
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": self.symbol,
                    "volume": pos.volume,
                    "type": (
                        mt5.ORDER_TYPE_SELL
                        if pos.type == mt5.POSITION_TYPE_BUY
                        else mt5.ORDER_TYPE_BUY
                    ),
                    "position": pos.ticket,
                    "price": price,
                    "deviation": 100,
                    "magic": 987654,
                    "comment": "ScalpingBot cierre por profit",
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                mt5.order_send(request)
                print(
                    f"[{datetime.now()}] Posición {pos.ticket} cerrada por profit {pos.profit:.2f}"
                )

            # Mover SL a breakeven
            elif pos.profit >= self.break_even_trigger:
                entry_price = pos.price_open
                tick = mt5.symbol_info_tick(self.symbol)
                sl_price = entry_price
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "symbol": self.symbol,
                    "position": pos.ticket,
                    "sl": sl_price,
                    "tp": pos.tp,
                }
                mt5.order_send(request)
                print(
                    f"[{datetime.now()}] SL de posición {pos.ticket} movido a break-even"
                )

    def run(self):
        self.connect()
        acc = mt5.account_info()
        self.account_balance = acc.balance
        self.start_equity = acc.equity

        print(
            f"Balance inicial: {self.account_balance}, Equity inicial: {self.start_equity}"
        )

        while True:
            equity = mt5.account_info().equity

            # Meta diaria alcanzada
            if (
                equity - self.start_equity
            ) / self.start_equity >= self.daily_profit_target:
                print(f"[{datetime.now()}] Meta diaria alcanzada, cerrando posiciones.")
                self.close_all_positions()
                break

            # Pérdida máxima alcanzada
            if (equity - self.start_equity) / self.start_equity <= -self.max_daily_loss:
                print(
                    f"[{datetime.now()}] Límite de pérdidas alcanzado, cerrando posiciones."
                )
                self.close_all_positions()
                break

            df = self.get_data()
            signal = self.check_signal(df)

            if signal and self.count_open_positions() < self.max_open_positions:
                self.place_order(signal, 0.01)

            # Revisión de profits individuales en cada ciclo
            self.check_individual_profits()

            time.sleep(1)  # revisar cada 1 segundos


if __name__ == "__main__":
    bot = ScalpingBot(symbol="XAUUSD", timeframe=mt5.TIMEFRAME_M1)
    bot.run()
