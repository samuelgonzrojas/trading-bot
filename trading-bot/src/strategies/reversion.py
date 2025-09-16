import pandas as pd
import numpy as np


class MeanReversionStrategy:
    def __init__(
        self, rsi_period=14, bb_period=20, bb_std=2, rsi_overbought=70, rsi_oversold=30
    ):
        self.rsi_period = rsi_period
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()

        # RSI
        delta = data["close"].diff()
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        roll_up = pd.Series(gain).rolling(self.rsi_period).mean()
        roll_down = pd.Series(loss).rolling(self.rsi_period).mean()
        rs = roll_up / (roll_down + 1e-9)
        data["rsi"] = 100 - (100 / (1 + rs))

        # Bandas de Bollinger
        data["ma"] = data["close"].rolling(self.bb_period).mean()
        data["std"] = data["close"].rolling(self.bb_period).std()
        data["upper"] = data["ma"] + self.bb_std * data["std"]
        data["lower"] = data["ma"] - self.bb_std * data["std"]

        # Señales
        data["signal"] = 0
        # Long cuando RSI < oversold y close < banda inferior
        data.loc[
            (data["rsi"] < self.rsi_oversold) & (data["close"] < data["lower"]),
            "signal",
        ] = 1
        # Short cuando RSI > overbought y close > banda superior
        data.loc[
            (data["rsi"] > self.rsi_overbought) & (data["close"] > data["upper"]),
            "signal",
        ] = -1

        return data
