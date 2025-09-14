import yaml
import pandas as pd
import yfinance as yf
from src.strategies.sma_crossover import SmaCrossoverStrategy


def load_config(path="/workspaces/trading-bot/trading-bot/config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def main():
    config = load_config()
    symbol = config["trading"]["symbol"]
    timeframe = config["trading"]["timeframe"]

    # 🔹 Descarga datos históricos con yfinance
    # Ajusta el periodo a lo que quieras probar: '1y', '6mo', etc.
    data = yf.download(symbol, period="6mo", interval=timeframe)

    if data.empty:
        print("No se descargaron datos, revisa el símbolo o la conexión a internet.")
        return

    # Solo nos interesa la columna de cierre
    df = data[["Close"]].rename(columns={"Close": "close"})

    # 🔹 Aplicar estrategia SMA
    strategy = SmaCrossoverStrategy(short_window=3, long_window=5)
    signals = strategy.generate_signals(df)

    # 🔹 Mostrar resultados
    print("Señales generadas:")
    print(signals.tail(10))  # Últimas 10 filas


if __name__ == "__main__":
    main()
