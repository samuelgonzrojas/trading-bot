import MetaTrader5 as mt5
from datetime import datetime, timedelta
from cls.tradingbot import FibonacciTradingBot

import warnings

warnings.filterwarnings("ignore")


# Función principal para elegir modo
def main():
    print("🎯 Bot de Trading con Fibonacci")
    print("=" * 40)
    print("1. Ejecutar Backtest (6 meses)")
    print("2. Trading en Vivo")

    choice = input("\nSelecciona una opción: ")

    # Configuración del bot
    bot = FibonacciTradingBot(
        symbol="EURUSD",
        timeframe=mt5.TIMEFRAME_M5,
        risk_per_trade=0.02,
        max_daily_trades=10,
    )

    if choice in ["1"]:
        # Ejecutar backtest
        print("\n📊 Ejecutando backtest de 6 meses...")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)

        bot.initialize_mt5()  # Necesario para obtener datos
        results = bot.backtest(
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
            initial_balance=1000,
        )

    if choice in ["2"]:
        # Trading en vivo
        print("\n🚀 Iniciando trading en vivo...")
        print("Presiona Ctrl+C para detener")
        bot.run_live_trading()


if __name__ == "__main__":
    main()
