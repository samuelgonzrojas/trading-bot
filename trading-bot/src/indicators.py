import talib


def add_indicators(df, rsi_period=14, atr_period=14):
    df["rsi"] = talib.RSI(df["close"].values, timeperiod=rsi_period)
    df["atr"] = talib.ATR(
        df["high"].values, df["low"].values, df["close"].values, timeperiod=atr_period
    )
    df["macd"], df["macd_signal"], df["macd_hist"] = talib.MACD(df["close"].values)
    df["ma_20"] = talib.SMA(df["close"].values, timeperiod=20)
    df["ma_50"] = talib.SMA(df["close"].values, timeperiod=50)
    return df
