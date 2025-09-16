import pandas as pd


class BreakoutStrategy:
    def __init__(self, bb_period=20, bb_std=2, atr_period=14):
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.atr_period = atr_period

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()

        # Bollinger Bands
        data["ma"] = data["close"].rolling(self.bb_period).mean()
        data["std"] = data["close"].rolling(self.bb_period).std()
        data["upper"] = data["ma"] + self.bb_std * data["std"]
        data["lower"] = data["ma"] - self.bb_std * data["std"]
        data["bandwidth"] = (data["upper"] - data["lower"]) / data["ma"]

        # ATR
        high_low = data["high"] - data["low"]
        high_close = (data["high"] - data["close"].shift()).abs()
        low_close = (data["low"] - data["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        data["atr"] = tr.rolling(self.atr_period).mean()

        # Señales
        data["signal"] = 0
        # Ruptura alcista: close > upper y bandwidth bajo antes (compresión)
        data.loc[
            (data["close"] > data["upper"])
            & (data["bandwidth"] < data["bandwidth"].rolling(50).quantile(0.2)),
            "signal",
        ] = 1
        # Ruptura bajista: close < lower y bandwidth bajo antes
        data.loc[
            (data["close"] < data["lower"])
            & (data["bandwidth"] < data["bandwidth"].rolling(50).quantile(0.2)),
            "signal",
        ] = -1

        return data
