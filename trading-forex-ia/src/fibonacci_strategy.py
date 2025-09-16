import pandas as pd
from src.indicators import add_indicators


class FibonacciStrategy:
    fib_levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    fib_extensions = [1.272, 1.414, 1.618, 2.0]

    def __init__(self, swing_period=20):
        self.swing_period = swing_period

    def find_swings(self, df):
        highs = df["high"].values
        lows = df["low"].values

        swing_highs = [
            (df.index[i], highs[i])
            for i in range(self.swing_period, len(highs) - self.swing_period)
            if highs[i] == max(highs[i - self.swing_period : i + self.swing_period + 1])
        ]
        swing_lows = [
            (df.index[i], lows[i])
            for i in range(self.swing_period, len(lows) - self.swing_period)
            if lows[i] == min(lows[i - self.swing_period : i + self.swing_period + 1])
        ]
        return swing_highs, swing_lows

    def generate_signal(self, df):
        df = add_indicators(df)
        swing_highs, swing_lows = self.find_swings(df)
        if len(swing_highs) < 1 or len(swing_lows) < 1:
            return 0, None, None, None

        current_price = df["close"].iloc[-1]
        trend = "up" if df["ma_20"].iloc[-1] > df["ma_50"].iloc[-1] else "down"

        # Ejemplo simplificado: señal si el precio toca nivel 0.618
        fib_level = swing_lows[-1][1] + (swing_highs[-1][1] - swing_lows[-1][1]) * 0.618
        tolerance = df["atr"].iloc[-1] * 0.3

        if abs(current_price - fib_level) <= tolerance:
            if trend == "up":
                sl = swing_lows[-1][1]
                tp = current_price + (current_price - sl) * 2
                return 1, current_price, sl, tp
            else:
                sl = swing_highs[-1][1]
                tp = current_price - (sl - current_price) * 2
                return -1, current_price, sl, tp
        return 0, None, None, None
