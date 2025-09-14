import yaml
import pandas as pd
from src.strategies.sma_crossover import SmaCrossoverStrategy


def load_config(path="/workspaces/trading-bot/trading-bot/config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def main():
    config = load_config()

    # 🔹 Simulación con datos ficticios
    data = pd.DataFrame({"close": [100, 101, 102, 103, 102, 101, 99, 98, 97, 99, 101]})

    strategy = SmaCrossoverStrategy(short_window=3, long_window=5)
    signals = strategy.generate_signals(data)

    print("Señales generadas:")
    print(signals[["close", "sma_short", "sma_long", "signal"]])


if __name__ == "__main__":
    main()
