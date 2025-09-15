import pandas as pd
from itertools import product


class SMAOptimizer:
    def __init__(self, backtester_class, initial_capital=1000, risk_per_trade=0.02):
        self.backtester_class = backtester_class
        self.initial_capital = initial_capital
        self.risk_per_trade = risk_per_trade
        self.results = []

    def generate_signals(self, data: pd.DataFrame, fast: int, slow: int):
        """
        Crea señales de compra/venta con SMA crossover
        """
        df = data.copy()
        df["fast_sma"] = df["close"].rolling(fast).mean()
        df["slow_sma"] = df["close"].rolling(slow).mean()
        df["signal"] = 0
        df.loc[df["fast_sma"] > df["slow_sma"], "signal"] = 1
        df.loc[df["fast_sma"] < df["slow_sma"], "signal"] = -1
        return df.dropna()

    def run(self, data: pd.DataFrame, fast_range, slow_range):
        """
        Ejecuta la optimización probando todas las combinaciones.
        fast_range: lista de posibles periodos para la media rápida
        slow_range: lista de posibles periodos para la media lenta
        """
        self.results = []
        for fast, slow in product(fast_range, slow_range):
            if fast >= slow:  # no tiene sentido una rápida >= lenta
                continue

            df_signals = self.generate_signals(data, fast, slow)

            bt = self.backtester_class(
                initial_capital=self.initial_capital,
                risk_per_trade=self.risk_per_trade,
            )
            res = bt.run(df_signals)

            self.results.append(
                {
                    "fast": fast,
                    "slow": slow,
                    "final_capital": res["final_capital"],
                    "profit": res["profit"],
                    "num_trades": len(res["trades"]),
                }
            )

        return pd.DataFrame(self.results).sort_values(
            by="final_capital", ascending=False
        )
