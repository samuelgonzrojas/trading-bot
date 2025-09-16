import time
from src.mt5_connector import MT5Connector
from src.fibonacci_strategy import FibonacciStrategy


def run_live():
    mt5_conn = MT5Connector(symbol="EURUSD")
    strategy = FibonacciStrategy()

    try:
        while True:
            df = mt5_conn.get_historical_data(100)
            signal, entry, sl, tp = strategy.generate_signal(df)
            if signal != 0:
                mt5_conn.place_order(signal, sl=sl, tp=tp)
            time.sleep(10)
    except KeyboardInterrupt:
        print("Trading detenido")
    finally:
        mt5_conn.shutdown()


if __name__ == "__main__":
    run_live()
