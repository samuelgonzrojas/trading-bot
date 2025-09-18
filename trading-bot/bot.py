import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime, timezone


class FibonacciBot:
    def __init__(self, symbol="XAUUSD", timeframe=mt5.TIMEFRAME_M15, risk=0.01):
        self.symbol = symbol
        self.timeframe = timeframe
        self.risk = risk
        self.daily_profit_target = 0.02  # 2%
        self.individual_profit_target = 0.005  # 0.5%
        self.account_balance = 0
        self.start_equity = 0
        self.max_open_positions = 5
        self.take_profit_multiplier = 0.5  # % del rango Fibonacci
        self.stop_loss_multiplier = 0.25  # % del rango Fibonacci

        print(f"FibonacciBot inicializado para {self.symbol}")

    def connect(self):
        if not mt5.initialize():
            print("Error al inicializar MetaTrader 5")
            raise RuntimeError("MT5 no se pudo inicializar")
        print("Conexión a MetaTrader 5 establecida")

    def get_data(self, n=500):
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, n)
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def calc_fibonacci(self, df):
        high = df["high"].tail(100).max()
        low = df["low"].tail(100).min()
        diff = high - low
        levels = {
            "0.0": high,
            "23.6": high - diff * 0.236,
            "38.2": high - diff * 0.382,
            "50.0": high - diff * 0.5,
            "61.8": high - diff * 0.618,
            "78.6": high - diff * 0.786,
            "100.0": low,
        }
        return levels, diff

    def check_signals(self, df, fib):
        last_close = df["close"].iloc[-1]

        # Señal de compra
        if abs(last_close - fib["38.2"]) < 0.5 or abs(last_close - fib["50.0"]) < 0.5:
            print(
                f"[{datetime.now()}] Señal COMPRA detectada cerca de niveles Fibonacci"
            )
            return "buy"

        # Señal de venta
        if abs(last_close - fib["61.8"]) < 0.5 or abs(last_close - fib["78.6"]) < 0.5:
            print(
                f"[{datetime.now()}] Señal VENTA detectada cerca de niveles Fibonacci"
            )
            return "sell"

        return None

    def count_open_positions(self):
        positions = mt5.positions_get(symbol=self.symbol)
        return len(positions) if positions else 0

    def check_individual_profits(self):
        """Monitorea posiciones individuales y cierra las que alcancen 0.5% de ganancia"""
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return

        print("-" * 50)

        for pos in positions:
            # Pintar valor de la posición que se está revisando
            print(
                f"[{datetime.now()}] Revisando posición {pos.ticket} con profit {pos.profit:.2f}"
            )

            position_value = pos.volume * 100000 * pos.price_open
            current_profit_pct = (pos.profit / position_value) * 100

            if current_profit_pct >= (
                self.individual_profit_target * 100
            ):  # 0.5% de ganancia
                # Cerrar la posición
                tick = mt5.symbol_info_tick(self.symbol)
                close_price = (
                    tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
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
                    "price": close_price,
                    "deviation": 100,
                    "magic": 123456,
                    "comment": "FibonacciBot - Ganancia 0.5%",
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }

                result = mt5.order_send(request)
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    print(
                        f"[{datetime.now()}] Posición {pos.ticket} cerrada con ganancia: {current_profit_pct:.2f}%"
                    )
                else:
                    print(
                        f"[{datetime.now()}] Error cerrando posición {pos.ticket}, Retcode={result.retcode}"
                    )

        total_profit = sum(pos.profit for pos in positions)
        print(
            f"[{datetime.now()}] Beneficio total de posiciones abiertas: {total_profit:.2f}"
        )
        print("-" * 50)

    def place_order(self, action, lot, fib_range):
        tick = mt5.symbol_info_tick(self.symbol)
        price = tick.ask if action == "buy" else tick.bid

        # SL y TP dinámicos según Fibonacci
        sl_distance = fib_range * self.stop_loss_multiplier
        tp_distance = fib_range * self.take_profit_multiplier
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
            "deviation": 100,
            "magic": 123456,
            "comment": "FibonacciBot",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            print(
                f"[{datetime.now()}] {action.upper()} ejecutada a {price:.2f} SL:{sl:.2f} TP:{tp:.2f}"
            )
        else:
            print(
                f"[{datetime.now()}] Error al ejecutar {action.upper()} Retcode={result.retcode}"
            )
        return result

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
                "deviation": 100,
                "magic": 123456,
                "comment": "FibonacciBot cierre forzado",
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            print(
                f"[{datetime.now()}] Cierre forzado posición {pos.ticket} Retcode={result.retcode}"
            )

    def run(self):
        self.connect()
        account_info = mt5.account_info()
        self.account_balance = account_info.balance
        self.start_equity = account_info.equity
        print(
            f"Bot iniciado. Balance: {self.account_balance:.2f}, Equity: {self.start_equity:.2f}"
        )

        while True:
            now = datetime.now(timezone.utc)

            # Evitar operar entre 23h y 03h
            if now.hour >= 22 or now.hour < 2:
                print(
                    f"[{now}] Horario restringido (22h-02h). No se opera por inestablidad."
                )
                if now.hour == 22 and now.minute == 0:
                    self.close_all_positions()
                time.sleep(600)
                continue

            # NUEVA FUNCIONALIDAD: Monitorear ganancias individuales
            self.check_individual_profits()

            # Comprobar meta diaria
            equity = mt5.account_info().equity
            if (
                equity - self.start_equity
            ) / self.start_equity >= self.daily_profit_target:
                print(f"[{datetime.now()}] Meta diaria alcanzada. Deteniendo bot.")
                break

            if (
                equity - self.start_equity
            ) / self.start_equity <= -0.01:  # pérdida del 1%
                print(
                    f"[{datetime.now()}] Pérdida límite alcanzada. Cerrando todas las posiciones."
                )
                self.close_all_positions()

            df = self.get_data()
            fib, fib_range = self.calc_fibonacci(df)
            signal = self.check_signals(df, fib)

            if signal:
                open_positions = self.count_open_positions()
                if open_positions < self.max_open_positions:
                    lot = 0.01
                    self.place_order(signal, lot, fib_range)
                else:
                    print(
                        f"[{datetime.now()}] {open_positions} posiciones abiertas, no se abren más."
                    )

            time.sleep(20)


if __name__ == "__main__":
    bot = FibonacciBot(symbol="XAUUSD", timeframe=mt5.TIMEFRAME_M15)
    bot.run()
