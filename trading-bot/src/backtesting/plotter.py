import matplotlib.pyplot as plt


def plot_signals(data, trades, symbol="AAPL", filename="signals.png"):
    plt.figure(figsize=(12, 6))

    # Precio y medias móviles
    plt.plot(data.index, data["close"], label="Precio", color="black")
    plt.plot(data.index, data["sma_short"], label="SMA Corta", alpha=0.7)
    plt.plot(data.index, data["sma_long"], label="SMA Larga", alpha=0.7)

    # Marcar BUY / SELL
    for trade in trades:
        if trade["type"] == "BUY":
            plt.scatter(
                trade["date"], trade["price"], marker="^", color="green", label="BUY"
            )
        elif trade["type"] == "SELL":
            plt.scatter(
                trade["date"], trade["price"], marker="v", color="red", label="SELL"
            )

    plt.title(f"Señales de Trading - {symbol}")
    plt.xlabel("Fecha")
    plt.ylabel("Precio")
    plt.legend()
    plt.grid(True)
    plt.show()
    plt.savefig(filename)
    print(f"Gráfico de señales guardado en {filename}")
    plt.close()


def plot_equity_curve(trades, initial_capital=1000, filename="equity_curve.png"):
    """Dibuja cómo evoluciona el capital a lo largo del tiempo"""
    capital = initial_capital
    equity = []

    for trade in trades:
        if trade["type"] == "SELL":
            # calcular PnL acumulado hasta ese trade
            capital += (
                trade["price"] - trades[trades.index(trade) - 1]["price"]
            ) * trade["shares"]
        equity.append(capital)

    plt.figure(figsize=(12, 4))
    plt.plot(range(len(equity)), equity, label="Evolución capital", color="blue")
    plt.title("Evolución del capital en el tiempo")
    plt.xlabel("Operaciones")
    plt.ylabel("Capital")
    plt.grid(True)
    plt.legend()
    plt.show()
    plt.savefig(filename)
    print(f"Curva de capital guardada en {filename}")
    plt.close()
