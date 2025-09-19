import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime, timezone
import yaml
import logging

# Configuración de logs
logging.basicConfig(
    filename="scalping_bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

config = yaml.safe_load(open("trading-bot/config.yaml", "r"))


class ScalpingBot:
    def __init__(self, symbol="XAUUSD", timeframe=mt5.TIMEFRAME_M1, risk=0.01):
        self.symbol = symbol
        self.timeframe = timeframe
        self.risk = risk
        self.daily_profit_target = 0.005
        self.max_daily_loss = 0.01
        self.account_balance = 0
        self.start_equity = 0
        self.max_trades_per_day = 5
        self.trades_today = 0

        # Configuración scalping
        self.min_profit_close = 5.0
        self.break_even_trigger = 3.0
        self.allowed_hours = range(7, 19)  # UTC

        self.name = config["broker"]["name"]
        self.login = config["broker"]["login"]
        self.password = config["broker"]["password"]
        self.server = config["broker"]["server"]

        print(f"ScalpingBot inicializado para {self.symbol}")
        logging.info("ScalpingBot inicializado para %s", self.symbol)

    def connect(self):
        if not mt5.initialize(login=self.login, password=self.password, server=self.server):
            raise RuntimeError(f"MT5 no se pudo inicializar: {mt5.last_error()}")
        print("Conectado a MetaTrader 5")
        logging.info("Conectado a MetaTrader 5")

    def get_data(self, n=200):
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, n)
        if rates is None:
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def check_signal(self, df):
        df["ema_fast"] = df["close"].ewm(span=9).mean()
        df["ema_slow"] = df["close"].ewm(span=21).mean()
        df["ema_trend"] = df["close"].ewm(span=200).mean()
        df["rsi"] = self.rsi(df["close"], period=14)

        # Compra
        if (
            df["ema_fast"].iloc[-2] < df["ema_slow"].iloc[-2]
            and df["ema_fast"].iloc[-1] > df["ema_slow"].iloc[-1]
            and df["close"].iloc[-1] > df["ema_trend"].iloc[-1]
            and df["rsi"].iloc[-1] > 55
        ):
            return "buy"

        # Venta
        if (
            df["ema_fast"].iloc[-2] > df["ema_slow"].iloc[-2]
            and df["ema_fast"].iloc[-1] < df["ema_slow"].iloc[-1]
            and df["close"].iloc[-1] < df["ema_trend"].iloc[-1]
            and df["rsi"].iloc[-1] < 45
        ):
            return "sell"

        return None

    @staticmethod
    def rsi(series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).ewm(span=period).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(span=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_lot_size(self, stop_loss_distance):
        symbol_info = mt5.symbol_info(self.symbol)
        balance = mt5.account_info().balance
        riesgo_en_usd = balance * self.risk

        tick_value = symbol_info.trade_tick_value
        tick_size = symbol_info.trade_tick_size

        valor_por_pip = tick_value / tick_size
        lote = riesgo_en_usd / (stop_loss_distance * valor_por_pip)

        lote = round(lote / symbol_info.volume_step) * symbol_info.volume_step
        return max(symbol_info.volume_min, min(symbol_info.volume_max, lote))

    def place_order(self, action, atr):
        tick = mt5.symbol_info_tick(self.symbol)
        point = mt5.symbol_info(self.symbol).point
        price = tick.ask if action == "buy" else tick.bid

        sl_distance = 1.5 * atr
        tp_distance = 2.0 * atr
        lot = self.calculate_lot_size(sl_distance)

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
            "comment": "ScalpingBot",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"[{datetime.now()}] ✅ {action.upper()} enviada. Lote={lot:.2f}")
            logging.info("Orden %s enviada. Lote=%.2f", action, lot)
            self.trades_today += 1
        else:
            print(f"[{datetime.now()}] ❌ Error orden {action.upper()} Retcode={result.retcode}")
            logging.error("Error orden %s retcode=%s", action, result.retcode)

    def check_market_conditions(self, df):
        spread = mt5.symbol_info_tick(self.symbol).ask - mt5.symbol_info_tick(self.symbol).bid
        atr = self.atr(df, 14)

        now = datetime.now(timezone.utc)
        if now.hour not in self.allowed_hours:
            return False, atr
        if spread > 15 * mt5.symbol_info(self.symbol).point:
            return False, atr
        if atr < 0.1:
            return False, atr
        return True, atr

    @staticmethod
    def atr(df, period=14):
        df["h-l"] = df["high"] - df["low"]
        df["h-c"] = abs(df["high"] - df["close"].shift())
        df["l-c"] = abs(df["low"] - df["close"].shift())
        tr = df[["h-l", "h-c", "l-c"]].max(axis=1)
        return tr.rolling(period).mean().iloc[-1]

    def run(self):
        self.connect()
        acc = mt5.account_info()
        self.account_balance = acc.balance
        self.start_equity = acc.equity
        last_time = None

        print(f"Balance inicial: {self.account_balance}, Equity: {self.start_equity}")

        while True:
            acc_info = mt5.account_info()
            equity = acc_info.equity

            if (equity - self.start_equity) / self.start_equity >= self.daily_profit_target:
                print("🎯 Meta diaria alcanzada")
                break
            if (equity - self.start_equity) / self.start_equity <= -self.max_daily_loss:
                print("🛑 Stop diario alcanzado")
                break
            if self.trades_today >= self.max_trades_per_day:
                print("⚠️ Límite de operaciones alcanzado")
                break

            df = self.get_data()
            if df is None:
                time.sleep(5)
                continue

            if last_time != df["time"].iloc[-1]:
                valid, atr = self.check_market_conditions(df)
                if valid:
                    signal = self.check_signal(df)
                    if signal and self.count_open_positions() == 0:
                        self.place_order(signal, atr)
                last_time = df["time"].iloc[-1]

            time.sleep(1)


if __name__ == "__main__":
    bot = ScalpingBot(symbol="XAUUSD", timeframe=mt5.TIMEFRAME_M1, risk=0.01)
    bot.run()