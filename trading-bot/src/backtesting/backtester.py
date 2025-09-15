import pandas as pd


class Backtester:
    def __init__(
        self,
        initial_capital=1000,
        risk_per_trade=0.02,
        spread=0.0002,  # 2 pips en EUR/USD
        commission_per_lot=7.0,  # USD por lote ida y vuelta
        lot_size=100000,  # 1 lote = 100k unidades
    ):
        self.initial_capital = initial_capital
        self.risk_per_trade = risk_per_trade
        self.spread = spread
        self.commission_per_lot = commission_per_lot
        self.lot_size = lot_size
        self.results = None
        self.trades = []

    def apply_costs(self, entry_price, exit_price, lots, is_buy):
        """
        Ajusta precios de entrada/salida con spread
        y calcula la comisión total.
        """
        if is_buy:
            entry_price += self.spread
            exit_price -= self.spread
        else:
            entry_price -= self.spread
            exit_price += self.spread

        commission = self.commission_per_lot * lots
        return entry_price, exit_price, commission

    def run(self, data: pd.DataFrame):
        """
        Ejecuta un backtest sobre las señales de la estrategia.
        data debe contener: 'close', 'signal'
        """
        capital = self.initial_capital
        position = 0  # volumen en lotes
        entry_price = 0

        for date, row in data.iterrows():
            price = row["close"]
            signal = row["signal"]

            # Entrar en largo
            if signal == 1 and position == 0:
                # Riesgo máximo por trade
                risk_amount = capital * self.risk_per_trade
                # Asumimos stop ~1% para definir tamaño de lote simplificado
                # (esto lo puedes mejorar más adelante)
                position = round(risk_amount / (price * 0.01 * self.lot_size), 2)
                if position <= 0:
                    continue
                entry_price = price
                self.trades.append(
                    {"date": date, "type": "BUY", "price": price, "lots": position}
                )

            # Salir de la posición
            elif signal == -1 and position > 0:
                adj_entry, adj_exit, commission = self.apply_costs(
                    entry_price, price, position, is_buy=True
                )
                profit = (adj_exit - adj_entry) * position * self.lot_size
                profit -= commission
                capital += profit
                self.trades.append(
                    {
                        "date": date,
                        "type": "SELL",
                        "price": price,
                        "lots": position,
                        "profit": profit,
                    }
                )
                position = 0

        self.results = {
            "final_capital": capital,
            "profit": capital - self.initial_capital,
            "trades": self.trades,
        }
        return self.results

    def summary(self):
        if not self.results:
            return "No se ha ejecutado el backtest."
        return (
            f"Capital inicial: {self.initial_capital}\n"
            f"Capital final: {self.results['final_capital']:.2f}\n"
            f"Ganancia neta: {self.results['profit']:.2f}\n"
            f"Número de operaciones: {len(self.results['trades'])}"
        )

    def export_trades(self, filename="/workspaces/trading-bot/trading-bot/trades.csv"):
        df = pd.DataFrame(self.trades)
        df.to_csv(filename, index=False)
        return filename
