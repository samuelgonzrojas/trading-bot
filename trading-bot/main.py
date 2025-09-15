from math import log
from os import path
import MetaTrader5 as mt5
import pandas as pd
import yaml
from src.strategies.sma_crossover import SmaCrossoverStrategy
from src.backtesting.backtester import Backtester
from src.strategies.smaoptimicer import SMAOptimizer


def load_config(path="trading-bot/config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def connect_mt5(name=None, account=None, password=None, server=None):
    """Inicializa MT5 y conecta a la cuenta demo"""
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
    else:
        print("Conectado a MT5 (sin login)")
    return True


def get_data(symbol="EURUSD", timeframe=mt5.TIMEFRAME_H1, n=500):
    """Obtiene OHLC histórico desde MT5"""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n)
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    df.rename(columns={"close": "close"}, inplace=True)
    return df


def main():
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

    optimizer = SMAOptimizer(Backtester, initial_capital=1000, risk_per_trade=0.02)

    # Probar medias rápidas 3 a 20 y lentas 30 a 100
    results = optimizer.run(data, fast_range=range(3, 21), slow_range=range(30, 101))

    print(results.head(10))  # top 10 combinaciones

    # Estrategia SMA
    strategy = SmaCrossoverStrategy(short_window=20, long_window=50)
    signals = strategy.generate_signals(data)

    # Backtesting
    backtester = Backtester(
        initial_capital=config["trading"]["capital"],
        risk_per_trade=config["trading"]["risk_per_trade"],
    )
    results = backtester.run(signals)

    print("=== RESULTADOS DEL BACKTEST ===")
    print(backtester.summary())

    # Guardar CSV y gráficos
    filename = backtester.export_trades("trading-bot/trades.csv")
    print(f"Operaciones guardadas en {filename}")

    # Cerrar MT5
    mt5.shutdown()


if __name__ == "__main__":
    main()
