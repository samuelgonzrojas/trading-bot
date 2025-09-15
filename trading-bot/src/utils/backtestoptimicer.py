import pandas as pd
from itertools import product


class RobustBacktester:
    def __init__(
        self,
        initial_capital=1000,
        risk_per_trade=0.02,
        spread=0.0002,
        commission_per_lot=7.0,
        lot_size=100000,
    ):
        self.initial_capital = initial_capital
        self.risk_per_trade = risk_per_trade
        self.spread = spread
        self.commission_per_lot = commission_per_lot
        self.lot_size = lot_size
        self.results = None
        self.trades = []

    @staticmethod
    def compute_rsi(data, period=14):
        delta = data["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def compute_atr(data, period=14):
        high_low = data["high"] - data["low"]
        high_close = (data["high"] - data["close"].shift()).abs()
        low_close = (data["low"] - data["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        return atr

    def apply_costs(self, entry_price, exit_price, lots, is_buy=True):
        if is_buy:
            entry_price += self.spread
            exit_price -= self.spread
        else:
            entry_price -= self.spread
            exit_price += self.spread
        commission = self.commission_per_lot * lots
        return entry_price, exit_price, commission

    def run(
        self,
        data,
        fast_ema,
        slow_ema,
        rsi_period,
        rsi_overbought,
        rsi_oversold,
        atr_period,
        stop_atr,
        take_atr,
    ):

        df = data.copy()
        df["ema_fast"] = df["close"].ewm(span=fast_ema, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=slow_ema, adjust=False).mean()
        df["rsi"] = self.compute_rsi(df, rsi_period)
        df["atr"] = self.compute_atr(df, atr_period)

        capital = self.initial_capital
        position = 0
        entry_price = 0
        stop_loss = 0
        take_profit = 0

        for date, row in df.iterrows():
            price = row["close"]
            rsi = row["rsi"]
            atr = row["atr"]
            ema_fast = row["ema_fast"]
            ema_slow = row["ema_slow"]

            # Entrada
            if position == 0 and ema_fast > ema_slow and rsi < rsi_overbought:
                risk_amount = capital * self.risk_per_trade
                position = round(risk_amount / (atr * self.lot_size), 2)
                if position <= 0:
                    continue
                entry_price = price
                stop_loss = price - stop_atr * atr
                take_profit = price + take_atr * atr

            # Salida
            elif position > 0:
                exit_signal = False
                if price <= stop_loss or price >= take_profit:
                    exit_signal = True
                elif ema_fast < ema_slow:
                    exit_signal = True

                if exit_signal:
                    adj_entry, adj_exit, commission = self.apply_costs(
                        entry_price, price, position
                    )
                    profit = (
                        adj_exit - adj_entry
                    ) * position * self.lot_size - commission
                    capital += profit
                    position = 0

        self.results = {
            "final_capital": capital,
            "profit": capital - self.initial_capital,
        }
        return self.results


class StrategyOptimizer:
    def __init__(self, data, backtester_class):
        self.data = data
        self.backtester_class = backtester_class
        self.results = []

    def optimize(
        self,
        fast_ema_range,
        slow_ema_range,
        rsi_period_range,
        rsi_overbought_range,
        rsi_oversold_range,
        atr_period_range,
        stop_atr_range,
        take_atr_range,
    ):

        for fast, slow, rsi_p, rsi_ob, rsi_os, atr_p, stop_atr, take_atr in product(
            fast_ema_range,
            slow_ema_range,
            rsi_period_range,
            rsi_overbought_range,
            rsi_oversold_range,
            atr_period_range,
            stop_atr_range,
            take_atr_range,
        ):

            if fast >= slow or rsi_os >= rsi_ob:
                continue

            bt = self.backtester_class()
            res = bt.run(
                self.data,
                fast_ema=fast,
                slow_ema=slow,
                rsi_period=rsi_p,
                rsi_overbought=rsi_ob,
                rsi_oversold=rsi_os,
                atr_period=atr_p,
                stop_atr=stop_atr,
                take_atr=take_atr,
            )

            self.results.append(
                {
                    "fast_ema": fast,
                    "slow_ema": slow,
                    "rsi_period": rsi_p,
                    "rsi_overbought": rsi_ob,
                    "rsi_oversold": rsi_os,
                    "atr_period": atr_p,
                    "stop_atr": stop_atr,
                    "take_atr": take_atr,
                    "final_capital": res["final_capital"],
                    "profit": res["profit"],
                }
            )

        df_res = pd.DataFrame(self.results).sort_values(
            by="final_capital", ascending=False
        )
        df_res.to_csv("optimization_results.csv", index=False)
        return df_res.head(10)  # top 10 combinaciones
