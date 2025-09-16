import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime


class MT5Connector:
    def __init__(self, symbol="EURUSD", timeframe=mt5.TIMEFRAME_M5):
        self.symbol = symbol
        self.timeframe = timeframe
        if not mt5.initialize():
            raise Exception("No se pudo inicializar MT5")

        # Asegurarse de que el símbolo está seleccionado
        if not mt5.symbol_select(self.symbol, True):
            raise Exception(f"Error al seleccionar símbolo {self.symbol}")

    def get_historical_data(self, n_bars=500):
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, n_bars)
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)
        return df

    def place_order(self, signal, volume=0.01, sl=None, tp=None):
        tick = mt5.symbol_info_tick(self.symbol)
        if signal == 1:
            price = tick.ask
            order_type = mt5.ORDER_TYPE_BUY
        elif signal == -1:
            price = tick.bid
            order_type = mt5.ORDER_TYPE_SELL
        else:
            return False

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl if sl else 0,
            "tp": tp if tp else 0,
            "deviation": 20,
            "magic": 123456,
            "comment": "Fibonacci_Trade",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        return result.retcode == mt5.TRADE_RETCODE_DONE

    def shutdown(self):
        mt5.shutdown()
