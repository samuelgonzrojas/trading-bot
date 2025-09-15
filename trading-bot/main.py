from src.strategies.sma_crossover import SmaCrossoverStrategy
from src.backtesting.backtester import Backtester
from src.backtesting.plotter import plot_signals, plot_equity_curve
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

    # Descargar datos
    data = yf.download(symbol, period="6mo", interval=timeframe)
    if isinstance(data.columns, pd.MultiIndex):
        data = data.swaplevel(axis=1)
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

    # Exportar trades
    filename = backtester.export_trades(
        "/workspaces/trading-bot/trading-bot/trades.csv"
    )
    print(f"Operaciones guardadas en {filename}")

    # Visualización
    plot_signals(
        signals,
        results["trades"],
        symbol=symbol,
        filename="/workspaces/trading-bot/trading-bot/src/backtesting/signals.png",
    )
    plot_equity_curve(
        results["trades"],
        initial_capital=config["trading"]["capital"],
        filename="/workspaces/trading-bot/trading-bot/src/backtesting/equity_curve.png",
    )


if __name__ == "__main__":
    main()
