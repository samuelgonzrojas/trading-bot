import pandas as pd
import numpy as np
import talib
import logging
from datetime import datetime


class Backtester:
    def __init__(self, strategy, initial_balance=1000, risk_per_trade=0.02):
        """
        Backtester simple para estrategias basadas en señales
        Args:
            strategy: objeto con método calculate_indicators(df) y generate_signals(df)
            initial_balance: capital inicial
            risk_per_trade: % riesgo por operación
        """
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.equity_curve = []
        self.trades = []

        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)

    def run(self, df):
        """
        Ejecutar backtest sobre un DataFrame con OHLCV
        """
        df = self.strategy.calculate_indicators(df)

        position = 0  # 0 = fuera, 1 = long, -1 = short
        entry_price = 0
        stop_loss = 0
        take_profit = 0

        for i in range(50, len(df)):  # empezamos después de calcular indicadores
            window = df.iloc[: i + 1]
            signal = self.strategy.generate_signals(window)

            current = df.iloc[i]

            # Si hay posición abierta, verificamos SL/TP
            if position != 0:
                if position == 1:  # Long
                    if current["low"] <= stop_loss:
                        self._close_trade(entry_price, stop_loss, "SL", current["time"])
                        position = 0
                    elif current["high"] >= take_profit:
                        self._close_trade(
                            entry_price, take_profit, "TP", current["time"]
                        )
                        position = 0

                elif position == -1:  # Short
                    if current["high"] >= stop_loss:
                        self._close_trade(entry_price, stop_loss, "SL", current["time"])
                        position = 0
                    elif current["low"] <= take_profit:
                        self._close_trade(
                            entry_price, take_profit, "TP", current["time"]
                        )
                        position = 0

            # Si no hay posición y aparece señal
            if position == 0 and signal != 0:
                atr = current["atr"]
                risk_amount = self.balance * self.risk_per_trade
                size = risk_amount / (atr * 2)  # lotaje simulado por ATR

                if signal == 1:  # Long
                    entry_price = current["close"]
                    stop_loss = entry_price - (atr * 2)
                    take_profit = entry_price + (atr * 3)
                    position = 1
                    self._open_trade(
                        entry_price,
                        stop_loss,
                        take_profit,
                        size,
                        "LONG",
                        current["time"],
                    )

                elif signal == -1:  # Short
                    entry_price = current["close"]
                    stop_loss = entry_price + (atr * 2)
                    take_profit = entry_price - (atr * 3)
                    position = -1
                    self._open_trade(
                        entry_price,
                        stop_loss,
                        take_profit,
                        size,
                        "SHORT",
                        current["time"],
                    )

            self.equity_curve.append(self.balance)

        self.logger.info(f"Backtest terminado. Balance final: {self.balance:.2f}")
        return pd.DataFrame(self.trades), self.equity_curve

    def _open_trade(self, entry, sl, tp, size, direction, time):
        # self.logger.info(
        #     f"Abrimos {direction} {size:.2f} a {entry:.5f}, SL {sl:.5f}, TP {tp:.5f}"
        # )
        self.trades.append(
            {
                "time": time,
                "type": "ENTRY",
                "direction": direction,
                "price": entry,
                "sl": sl,
                "tp": tp,
                "balance": self.balance,
            }
        )

    def _close_trade(self, entry, exit_price, reason, time):
        pnl = (
            exit_price - entry
            if reason == "TP" or reason == "SL" and entry < exit_price
            else entry - exit_price
        )
        self.balance += pnl  # simplificación (no ajusta por lotaje real)
        # self.logger.info(
        #     f"🔒 Cerramos trade en {exit_price:.5f} por {reason}. Nuevo balance: {self.balance:.2f}"
        # )
        self.trades.append(
            {
                "time": time,
                "type": "EXIT",
                "reason": reason,
                "price": exit_price,
                "balance": self.balance,
            }
        )
