from src.strategies.sma_crossover import SmaCrossoverStrategy
from src.backtesting.backtester import Backtester
import pandas as pd
import yfinance as yf
import yaml


def load_config(path="/workspaces/trading-bot/trading-bot/config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def main():
    config = load_config()
    symbol = config["trading"]["symbol"]
    timeframe = config["trading"]["timeframe"]

    # 📈 Descargar datos reales
    data = yf.download(symbol, period="6mo", interval=timeframe)

    # Si devuelve MultiIndex, lo aplanamos
    if isinstance(data.columns, pd.MultiIndex):
        data = data.swaplevel(axis=1)  # cambia orden (ticker primero)
        data = data[symbol]

    data = data.rename(columns={"Close": "close"})

    # Estrategia
    strategy = SmaCrossoverStrategy(short_window=3, long_window=5)
    signals = strategy.generate_signals(data)

    # Backtesting
    backtester = Backtester(
        initial_capital=config["trading"]["capital"],
        risk_per_trade=config["trading"]["risk_per_trade"],
    )
    results = backtester.run(signals)

    print("=== RESULTADOS DEL BACKTEST ===")
    print(backtester.summary())


if __name__ == "__main__":
    main()
