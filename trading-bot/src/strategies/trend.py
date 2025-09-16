import pandas as pd


class TrendStrategy:
    def __init__(
        self,
        ema_fast=20,
        ema_slow=100,
        rsi_period=14,
        rsi_overbought=70,
        rsi_oversold=30,
    ):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold

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

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df["ema_fast"] = df["close"].ewm(span=self.ema_fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.ema_slow, adjust=False).mean()
        df["rsi"] = self.compute_rsi(df, self.rsi_period)

        df["signal"] = 0
        # Entrada larga: tendencia alcista + RSI no sobrecomprado
        df.loc[
            (df["ema_fast"] > df["ema_slow"]) & (df["rsi"] < self.rsi_overbought),
            "signal",
        ] = 1
        # Entrada corta: tendencia bajista + RSI no sobrevendido
        df.loc[
            (df["ema_fast"] < df["ema_slow"]) & (df["rsi"] > self.rsi_oversold),
            "signal",
        ] = -1

        return df
