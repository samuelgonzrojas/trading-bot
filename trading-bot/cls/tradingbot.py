import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime
import talib
import warnings

warnings.filterwarnings("ignore")


class FibonacciTradingBot:
    def __init__(
        self,
        symbol="EURUSD",
        timeframe=mt5.TIMEFRAME_M5,
        risk_per_trade=0.02,
        max_daily_trades=20,
    ):
        """
        Bot de trading con estrategia Fibonacci + backtesting

        Args:
            symbol: Par de divisas a operar
            timeframe: Marco temporal
            risk_per_trade: Riesgo por operación
            max_daily_trades: Máximo número de operaciones diarias
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.risk_per_trade = risk_per_trade
        self.max_daily_trades = max_daily_trades
        self.daily_trades = 0
        self.last_trade_date = None

        # Niveles de Fibonacci
        self.fib_levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        self.fib_extension_levels = [1.272, 1.414, 1.618, 2.0, 2.618]

        # Configuración de indicadores
        self.swing_period = 20  # Período para detectar swings
        self.atr_period = 14
        self.rsi_period = 14

        # Variables para backtesting
        self.backtest_results = []
        self.trades_history = []

        # Configurar logging
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)

        # Variables de estado
        self.current_swing_high = None
        self.current_swing_low = None
        self.fib_levels_calculated = {}

    def initialize_mt5(self):
        """Inicializar conexión con MetaTrader 5"""
        if not mt5.initialize():
            self.logger.error("Error al inicializar MT5")
            return False

        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            self.logger.error(f"Símbolo {self.symbol} no encontrado")
            return False

        if not symbol_info.visible:
            if not mt5.symbol_select(self.symbol, True):
                self.logger.error(f"Error al seleccionar símbolo {self.symbol}")
                return False

        self.logger.info("MT5 inicializado correctamente")
        return True

    def get_market_data(self, start_date=None, end_date=None, bars=300):
        """Obtener datos del mercado"""
        if start_date:
            rates = mt5.copy_rates_range(
                self.symbol, self.timeframe, start_date, end_date
            )
        else:
            rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, bars)

        if rates is None:
            self.logger.error("Error al obtener datos del mercado")
            return None

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)
        return df

    def find_swing_points(self, df):
        """Encontrar puntos de swing (máximos y mínimos significativos)"""
        high_values = df["high"].values
        low_values = df["low"].values

        # Encontrar máximos locales
        swing_highs = []
        for i in range(self.swing_period, len(high_values) - self.swing_period):
            if high_values[i] == max(
                high_values[i - self.swing_period : i + self.swing_period + 1]
            ):
                swing_highs.append((df.index[i], high_values[i]))

        # Encontrar mínimos locales
        swing_lows = []
        for i in range(self.swing_period, len(low_values) - self.swing_period):
            if low_values[i] == min(
                low_values[i - self.swing_period : i + self.swing_period + 1]
            ):
                swing_lows.append((df.index[i], low_values[i]))

        return swing_highs, swing_lows

    def calculate_fibonacci_levels(self, swing_high, swing_low, trend_direction="up"):
        """Calcular niveles de Fibonacci"""
        high_price = swing_high[1]
        low_price = swing_low[1]
        diff = high_price - low_price

        fib_levels = {}

        if trend_direction == "up":
            # Retroceso de Fibonacci para tendencia alcista
            for level in self.fib_levels:
                fib_levels[f"fib_{level}"] = high_price - (diff * level)

            # Extensiones para objetivos
            for i, level in enumerate(self.fib_extension_levels):
                fib_levels[f"ext_{level}"] = high_price + (diff * (level - 1))
        else:
            # Retroceso de Fibonacci para tendencia bajista
            for level in self.fib_levels:
                fib_levels[f"fib_{level}"] = low_price + (diff * level)

            # Extensiones para objetivos
            for i, level in enumerate(self.fib_extension_levels):
                fib_levels[f"ext_{level}"] = low_price - (diff * (level - 1))

        return fib_levels

    def calculate_indicators(self, df):
        """Calcular indicadores técnicos adicionales"""
        # RSI
        df["rsi"] = talib.RSI(df["close"].values, timeperiod=self.rsi_period)

        # ATR
        df["atr"] = talib.ATR(
            df["high"].values,
            df["low"].values,
            df["close"].values,
            timeperiod=self.atr_period,
        )

        # MACD
        df["macd"], df["macd_signal"], df["macd_hist"] = talib.MACD(
            df["close"].values, fastperiod=12, slowperiod=26, signalperiod=9
        )

        # Medias móviles para confirmar tendencia
        df["ma_20"] = talib.SMA(df["close"].values, timeperiod=20)
        df["ma_50"] = talib.SMA(df["close"].values, timeperiod=50)

        return df

    def detect_fibonacci_signals(self, df, swing_highs, swing_lows):
        """Detectar señales de trading basadas en niveles de Fibonacci"""
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return 0, None, None, None

        current_price = df["close"].iloc[-1]
        current_time = df.index[-1]

        # Determinar la tendencia reciente
        recent_high = max(swing_highs, key=lambda x: x[0])
        recent_low = max(swing_lows, key=lambda x: x[0])

        trend_direction = "up" if recent_low[0] > recent_high[0] else "down"

        # Calcular niveles de Fibonacci
        if trend_direction == "up":
            # Buscar el swing low más reciente antes del último swing high
            valid_lows = [low for low in swing_lows if low[0] < recent_high[0]]
            if not valid_lows:
                return 0, None, None, None
            swing_low_for_calc = max(valid_lows, key=lambda x: x[0])
            fib_levels = self.calculate_fibonacci_levels(
                recent_high, swing_low_for_calc, "up"
            )

        else:
            # Buscar el swing high más reciente antes del último swing low
            valid_highs = [high for high in swing_highs if high[0] < recent_low[0]]
            if not valid_highs:
                return 0, None, None, None
            swing_high_for_calc = max(valid_highs, key=lambda x: x[0])
            fib_levels = self.calculate_fibonacci_levels(
                swing_high_for_calc, recent_low, "down"
            )

        # Buscar señales de compra/venta en niveles clave
        signal = 0
        entry_price = current_price
        stop_loss = None
        take_profit = None

        # Niveles clave de Fibonacci para entradas
        key_levels = [0.382, 0.5, 0.618]

        for level in key_levels:
            fib_price = fib_levels.get(f"fib_{level}")
            if fib_price is None:
                continue

            # Tolerancia para considerar que el precio está en el nivel
            tolerance = df["atr"].iloc[-1] * 0.3

            if abs(current_price - fib_price) <= tolerance:
                # Confirmaciones adicionales
                rsi_confirmation = self.check_rsi_confirmation(df, trend_direction)
                macd_confirmation = self.check_macd_confirmation(df, trend_direction)

                if rsi_confirmation and macd_confirmation:
                    if trend_direction == "up":
                        signal = 1  # Compra
                        stop_loss = fib_levels.get(
                            "fib_0.786", current_price - df["atr"].iloc[-1] * 2
                        )
                        take_profit = fib_levels.get(
                            "ext_1.618", current_price + df["atr"].iloc[-1] * 3
                        )
                    else:
                        signal = -1  # Venta
                        stop_loss = fib_levels.get(
                            "fib_0.786", current_price + df["atr"].iloc[-1] * 2
                        )
                        take_profit = fib_levels.get(
                            "ext_1.618", current_price - df["atr"].iloc[-1] * 3
                        )

                    break

        return signal, entry_price, stop_loss, take_profit

    def check_rsi_confirmation(self, df, trend_direction):
        """Verificar confirmación con RSI"""
        rsi = df["rsi"].iloc[-1]
        if trend_direction == "up":
            return 30 < rsi < 60  # RSI no sobrecomprado, espacio para subir
        else:
            return 40 < rsi < 70  # RSI no sobrevendido, espacio para bajar

    def check_macd_confirmation(self, df, trend_direction):
        """Verificar confirmación con MACD"""
        macd = df["macd"].iloc[-1]
        macd_signal = df["macd_signal"].iloc[-1]

        if trend_direction == "up":
            return macd > macd_signal  # MACD bullish
        else:
            return macd < macd_signal  # MACD bearish

    def backtest(self, start_date, end_date, initial_balance=1000):
        """Ejecutar backtesting de la estrategia"""
        self.logger.info(f"Iniciando backtest desde {start_date} hasta {end_date}")

        # Obtener datos históricos
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        total_days = (end_dt - start_dt).days

        df = self.get_market_data(start_date=start_dt, end_date=end_dt)
        if df is None:
            self.logger.error("No se pudieron obtener datos para backtest")
            return None

        # Filtrar por fechas
        df = df[start_date:end_date]
        df = self.calculate_indicators(df)

        # Variables de backtesting
        balance = initial_balance
        trades = []
        equity_curve = []
        daily_returns = []

        # Simular trading
        for i in range(100, len(df)):  # Empezar después de tener suficientes datos
            print(i)
            current_df = df.iloc[: i + 1]
            swing_highs, swing_lows = self.find_swing_points(current_df)

            signal, entry_price, stop_loss, take_profit = self.detect_fibonacci_signals(
                current_df, swing_highs, swing_lows
            )

            if signal != 0:
                # Calcular tamaño de posición
                risk_amount = balance * self.risk_per_trade
                stop_loss_pips = (
                    abs(entry_price - stop_loss) / mt5.symbol_info(self.symbol).point
                    if stop_loss
                    else 50
                )
                position_size = risk_amount / (stop_loss_pips * 10)  # Simplificado

                # Simular resultado del trade
                trade_result = self.simulate_trade_result(
                    df.iloc[i + 1 : i + 50] if i + 50 < len(df) else df.iloc[i + 1 :],
                    signal,
                    entry_price,
                    stop_loss,
                    take_profit,
                    position_size,
                )

                if trade_result:
                    trades.append(
                        {
                            "date": df.index[i],
                            "signal": signal,
                            "entry_price": entry_price,
                            "exit_price": trade_result["exit_price"],
                            "pnl": trade_result["pnl"],
                            "balance": balance + trade_result["pnl"],
                        }
                    )

                    balance += trade_result["pnl"]
                    daily_returns.append(trade_result["pnl"] / balance)

            equity_curve.append({"date": df.index[i], "balance": balance})

        # Calcular estadísticas
        stats = self.calculate_backtest_statistics(
            trades, initial_balance, daily_returns
        )

        # Guardar resultados
        self.backtest_results = {
            "trades": trades,
            "equity_curve": equity_curve,
            "statistics": stats,
            "final_balance": balance,
        }

        return self.backtest_results

    def simulate_trade_result(
        self, future_df, signal, entry_price, stop_loss, take_profit, position_size
    ):
        """Simular el resultado de un trade"""
        if len(future_df) == 0:
            return None

        for idx, row in future_df.iterrows():
            if signal == 1:  # Long
                if stop_loss and row["low"] <= stop_loss:
                    pnl = (
                        (stop_loss - entry_price) * position_size * 100000
                    )  # Simplificado
                    return {"exit_price": stop_loss, "pnl": pnl}
                elif take_profit and row["high"] >= take_profit:
                    pnl = (take_profit - entry_price) * position_size * 100000
                    return {"exit_price": take_profit, "pnl": pnl}
            else:  # Short
                if stop_loss and row["high"] >= stop_loss:
                    pnl = (entry_price - stop_loss) * position_size * 100000
                    return {"exit_price": stop_loss, "pnl": pnl}
                elif take_profit and row["low"] <= take_profit:
                    pnl = (entry_price - take_profit) * position_size * 100000
                    return {"exit_price": take_profit, "pnl": pnl}

        # Si no se cerró, cerrar al final del período
        exit_price = future_df["close"].iloc[-1]
        if signal == 1:
            pnl = (exit_price - entry_price) * position_size * 100000
        else:
            pnl = (entry_price - exit_price) * position_size * 100000

        return {"exit_price": exit_price, "pnl": pnl}

    def calculate_backtest_statistics(self, trades, initial_balance, daily_returns):
        """Calcular estadísticas del backtest"""
        if not trades:
            return {}

        df_trades = pd.DataFrame(trades)

        total_trades = len(trades)
        winning_trades = len(df_trades[df_trades["pnl"] > 0])
        losing_trades = len(df_trades[df_trades["pnl"] < 0])

        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0

        total_pnl = df_trades["pnl"].sum()
        avg_win = (
            df_trades[df_trades["pnl"] > 0]["pnl"].mean() if winning_trades > 0 else 0
        )
        avg_loss = (
            df_trades[df_trades["pnl"] < 0]["pnl"].mean() if losing_trades > 0 else 0
        )

        profit_factor = (
            abs(avg_win * winning_trades / (avg_loss * losing_trades))
            if avg_loss != 0
            else 0
        )

        final_balance = initial_balance + total_pnl
        total_return = (final_balance / initial_balance - 1) * 100

        # Drawdown máximo
        equity_curve = df_trades["balance"].values
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (peak - equity_curve) / peak * 100
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0

        # Sharpe ratio simplificado
        if daily_returns:
            sharpe_ratio = (
                np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252)
                if np.std(daily_returns) > 0
                else 0
            )
        else:
            sharpe_ratio = 0

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "total_return": total_return,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
        }

    def place_order(self, signal, entry_price, stop_loss, take_profit):
        """Colocar orden en el mercado (trading en vivo)"""
        if signal == 0:
            return False

        # Calcular tamaño de posición
        account_info = mt5.account_info()
        if account_info is None:
            return False

        balance = account_info.balance
        risk_amount = balance * self.risk_per_trade

        if stop_loss:
            stop_loss_pips = (
                abs(entry_price - stop_loss) / mt5.symbol_info(self.symbol).point
            )
            position_size = risk_amount / (stop_loss_pips * 10)  # Simplificado
        else:
            position_size = 0.01

        # Ajustar tamaño mínimo/máximo
        symbol_info = mt5.symbol_info(self.symbol)
        position_size = max(
            symbol_info.volume_min, min(symbol_info.volume_max, position_size)
        )
        position_size = (
            round(position_size / symbol_info.volume_step) * symbol_info.volume_step
        )

        # Crear solicitud de orden
        if signal == 1:  # Compra
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(self.symbol).ask
        else:  # Venta
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(self.symbol).bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": position_size,
            "type": order_type,
            "price": price,
            "sl": stop_loss if stop_loss else 0,
            "tp": take_profit if take_profit else 0,
            "deviation": 20,
            "magic": 987654,
            "comment": f"Fibonacci_Trade_{datetime.now().strftime('%H%M%S')}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # Enviar orden
        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(f"Error al enviar orden: {result.retcode}")
            return False

        self.daily_trades += 1
        direction = "COMPRA" if signal == 1 else "VENTA"
        self.logger.info(
            f"🎯 Orden Fibonacci {direction} ejecutada: {position_size} lotes a {price}"
        )
        return True

    def run_live_trading(self, check_interval=10):
        """Ejecutar trading en vivo"""
        self.logger.info(
            f"🚀 Iniciando trading en vivo con estrategia Fibonacci para {self.symbol}"
        )

        if not self.initialize_mt5():
            return

        try:
            while True:
                # Verificar límite diario
                current_date = datetime.now().date()
                if self.last_trade_date != current_date:
                    self.daily_trades = 0
                    self.last_trade_date = current_date

                if self.daily_trades >= self.max_daily_trades:
                    self.logger.info("📊 Límite diario de operaciones alcanzado")
                    time.sleep(3600)
                    continue

                # Obtener datos del mercado
                df = self.get_market_data()
                if df is None:
                    time.sleep(5)
                    continue

                # Calcular indicadores
                df = self.calculate_indicators(df)

                # Encontrar puntos de swing
                swing_highs, swing_lows = self.find_swing_points(df)

                # Detectar señales de Fibonacci
                signal, entry_price, stop_loss, take_profit = (
                    self.detect_fibonacci_signals(df, swing_highs, swing_lows)
                )

                # Ejecutar orden si hay señal
                if signal != 0:
                    positions = mt5.positions_get(symbol=self.symbol)
                    open_positions = len(positions) if positions else 0

                    if open_positions < 2:  # Máximo 2 posiciones simultáneas
                        self.place_order(signal, entry_price, stop_loss, take_profit)

                        # Log de la señal
                        direction = "COMPRA" if signal == 1 else "VENTA"
                        self.logger.info(
                            f"📈 Señal {direction} - Entry: {entry_price:.5f}, "
                            f"SL: {stop_loss:.5f}, TP: {take_profit:.5f}"
                        )

                # Estado actual
                current_positions = mt5.positions_get(symbol=self.symbol)
                pos_count = len(current_positions) if current_positions else 0
                current_price = mt5.symbol_info_tick(self.symbol).bid

                self.logger.info(
                    f"📊 Estado: {pos_count} posiciones, "
                    f"{self.daily_trades}/{self.max_daily_trades} trades hoy, "
                    f"Precio: {current_price:.5f}"
                )

                time.sleep(check_interval)

        except KeyboardInterrupt:
            self.logger.info("Trading detenido por el usuario")
        except Exception as e:
            self.logger.error(f"Error en trading en vivo: {e}")
        finally:
            mt5.shutdown()
