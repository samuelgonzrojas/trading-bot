import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from src.mt5_connector import MT5Connector
from src.fibonacci_strategy import FibonacciStrategy


def run_backtest(initial_balance=1000):
    mt5_conn = MT5Connector(symbol="EURUSD")
    df = mt5_conn.get_historical_data(1000)
    mt5_conn.shutdown()

    strategy = FibonacciStrategy()
    balance = initial_balance
    equity_curve = []
    trades = []

    for i in range(50, len(df)):
        df_slice = df.iloc[: i + 1]
        signal, entry, sl, tp = strategy.generate_signal(df_slice)

        if signal != 0:
            # Simular trade: cierre al siguiente cierre o al TP/SL
            future_df = (
                df.iloc[i + 1 : i + 21] if i + 21 < len(df) else df.iloc[i + 1 :]
            )
            exit_price = None
            pnl = 0

            for _, row in future_df.iterrows():
                if signal == 1:  # Buy
                    if sl and row["low"] <= sl:
                        exit_price = sl
                        pnl = exit_price - entry
                        break
                    elif tp and row["high"] >= tp:
                        exit_price = tp
                        pnl = exit_price - entry
                        break
                else:  # Sell
                    if sl and row["high"] >= sl:
                        exit_price = sl
                        pnl = entry - exit_price
                        break
                    elif tp and row["low"] <= tp:
                        exit_price = tp
                        pnl = entry - exit_price
                        break

            if exit_price is None:
                exit_price = future_df["close"].iloc[-1]
                pnl = (exit_price - entry) if signal == 1 else (entry - exit_price)

            # Actualizar balance
            balance += pnl
            trades.append({"entry": entry, "exit": exit_price, "pnl": pnl})
        equity_curve.append(balance)

    # Estadísticas
    df_trades = pd.DataFrame(trades)
    total_trades = len(trades)
    winning_trades = len(df_trades[df_trades["pnl"] > 0])
    losing_trades = len(df_trades[df_trades["pnl"] < 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    total_pnl = df_trades["pnl"].sum() if total_trades > 0 else 0
    max_drawdown = np.max(np.maximum.accumulate(equity_curve) - equity_curve)
    sharpe_ratio = (
        (np.mean(df_trades["pnl"]) / np.std(df_trades["pnl"]) * np.sqrt(252))
        if total_trades > 1
        else 0
    )

    print(f"Total trades: {total_trades}")
    print(f"Winning trades: {winning_trades}, Losing trades: {losing_trades}")
    print(f"Win rate: {win_rate:.2f}%")
    print(f"Total PnL: {total_pnl:.2f}")
    print(f"Max Drawdown: {max_drawdown:.2f}")
    print(f"Sharpe Ratio: {sharpe_ratio:.2f}")

    # Plot equity curve
    plt.figure(figsize=(12, 6))
    plt.plot(equity_curve, label="Equity Curve")
    plt.title("Backtest Equity Curve")
    plt.xlabel("Bars")
    plt.ylabel("Balance")
    plt.legend()
    plt.show()


if __name__ == "__main__":
    run_backtest()
