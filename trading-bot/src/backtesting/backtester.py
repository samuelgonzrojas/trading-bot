import pandas as pd


class Backtester:
    def __init__(self, initial_capital=1000, risk_per_trade=0.02):
        self.initial_capital = initial_capital
        self.risk_per_trade = risk_per_trade
        self.results = None

    def run(self, data: pd.DataFrame):
        """
        Ejecuta un backtest sobre las señales de la estrategia.
        data debe contener: 'close', 'signal'
        """
        capital = self.initial_capital
        position = 0  # número de acciones en cartera
        trades = []

        for date, row in data.iterrows():
            price = row["close"]
            signal = row["signal"]

            # Entrar en largo
            if signal == 1 and position == 0:
                # tamaño de la posición en función del riesgo
                # risk_amount = capital * self.risk_per_trade
                # position = risk_amount // price  # número de acciones enteras
                position = capital // price  # comprar con todo el capital disponible
                entry_price = price
                trades.append(
                    {"date": date, "type": "BUY", "price": price, "shares": position}
                )

            # Salir de la posición
            elif signal == -1 and position > 0:
                capital += position * (price - entry_price)  # beneficio/pérdida
                trades.append(
                    {"date": date, "type": "SELL", "price": price, "shares": position}
                )
                position = 0

        # Guardar resultados
        self.results = {
            "final_capital": capital,
            "profit": capital - self.initial_capital,
            "trades": trades,
        }
        return self.results

    def summary(self):
        """Devuelve un resumen legible de los resultados."""
        if not self.results:
            return "No se ha ejecutado el backtest."
        return (
            f"Capital inicial: {self.initial_capital}\n"
            f"Capital final: {self.results['final_capital']:.2f}\n"
            f"Ganancia neta: {self.results['profit']:.2f}\n"
            f"Número de operaciones: {len(self.results['trades'])}"
        )
