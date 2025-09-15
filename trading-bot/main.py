import MetaTrader5 as mt5
import pandas as pd
import yaml
from src.backtesting.backtester import Backtester


def load_config(path="trading-bot/config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def connect_mt5(name=None, account=None, password=None, server=None):
    """Conecta a MetaTrader5"""
    if not mt5.initialize(
        login=account,
        password=password,
        server=server,
    ):
        print(f"Error al inicializar MT5: {mt5.last_error()}")
        return False

    if account and password and server:
        authorized = mt5.login(account, password, server=server)
        if authorized:
            print(f"Conectado a la cuenta {name} en {server}")
        else:
            print("Error de login:", mt5.last_error())
            return False

    return True


def get_data(symbol="EURUSD", timeframe=mt5.TIMEFRAME_H1, n=10000):
    """Obtiene datos históricos desde MetaTrader5"""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n)
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    df.rename(columns={"close": "close"}, inplace=True)
    return df


if __name__ == "__main__":
    config = load_config()
    symbol = config["trading"]["symbol"]
    timeframe_str = config["trading"]["timeframe"]

    # Mapeo simple timeframe a MT5
    timeframe_dict = {
        "1m": mt5.TIMEFRAME_M1,
        "5m": mt5.TIMEFRAME_M5,
        "15m": mt5.TIMEFRAME_M15,
        "1h": mt5.TIMEFRAME_H1,
        "4h": mt5.TIMEFRAME_H4,
        "1d": mt5.TIMEFRAME_D1,
    }
    timeframe = timeframe_dict.get(timeframe_str, mt5.TIMEFRAME_H1)

    # Conexión MT5
    connect_mt5(
        name=config["broker"]["name"],
        account=config["broker"]["login"],
        password=config["broker"]["password"],
        server=config["broker"]["server"],
    )

    # Descargar datos
    data = get_data(symbol=symbol, timeframe=timeframe, n=500)

    # Backtesting con parámetros ganadores
    backtester = Backtester(
        initial_capital=config["trading"]["capital"],
        risk_per_trade=config["trading"]["risk_per_trade"],
    )

    # Ejecuta el backtest directamente sobre los datos descargados
    results = backtester.run(
        data,
        fast_ema=10,
        slow_ema=30,
        rsi_overbought=75,
        rsi_oversold=25,
        atr_period=14,
        stop_atr=2.0,
        take_atr=2.0,
    )

    print("=== RESULTADOS DEL BACKTEST ===")
    print(backtester.summary())
