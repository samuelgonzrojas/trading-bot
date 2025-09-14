# Trading Bot en Python

Proyecto de trading algorítmico modular en Python, diseñado para:
- Aprender y experimentar con estrategias de trading.
- Probar estrategias con **datos históricos** (backtesting).
- Simular operaciones en **modo demo/paper trading**.
- Escalar a trading real en el futuro.

---

## Descripción

Este proyecto implementa un **bot de trading** basado en estrategias definidas por el usuario.  
La arquitectura está pensada para que sea **modular, extensible y mantenible**, con capas separadas para:

1. **Data Layer**: ingestión de datos históricos y en tiempo real.
2. **Strategies**: implementación de estrategias (ej. SMA crossover).
3. **Execution**: conexión con brokers/APIs.
4. **Backtesting**: simulación de operaciones sobre datos históricos.
5. **Portfolio & Risk Management**: gestión de capital, tamaño de posición y control de riesgo.
6. **Utils**: utilidades como logging y cálculo de indicadores.

Actualmente incluye un ejemplo de estrategia **SMA crossover** aplicada sobre datos históricos de Yahoo Finance.

---

## Estructura del proyecto

trading-bot/
├── src/
│ ├── strategies/ # Estrategias de trading
│ ├── backtesting/ # Motor de backtesting
│ ├── execution/ # Conexión con brokers
│ ├── portfolio/ # Gestión de riesgo y capital
│ └── utils/ # Funciones auxiliares y logging
├── tests/ # Pruebas unitarias
├── notebooks/ # Notebooks para análisis y experimentación
├── data/ # Datos históricos y logs
├── config.yaml # Configuración del bot
└── requirements.txt # Dependencias del proyecto

## Instalación

1. Clonar el repositorio:
```bash
git clone https://github.com/TU_USUARIO/trading-bot.git
cd trading-bot
```

2. Crear y activar un entorno virtual:
```bash
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

## Configuración

Editar config.yaml para definir:
```yaml
trading:
  symbol: "AAPL"        # Activo financiero
  timeframe: "1d"       # '1d', '1h', '15m', etc.
  capital: 1000         # Capital inicial de la simulación
  risk_per_trade: 0.02  # Riesgo máximo por operación (2%)
```

## Uso

Ejecutar el script principal:
```bash
python src/main.py
```

Esto descargará datos históricos, aplicará la estrategia SMA y mostrará las señales generadas.

## Próximos pasos

- Integrar backtesting completo para evaluar estrategias.
- Conectar con broker demo para paper trading.
- Añadir más indicadores y estrategias avanzadas.
- Implementar gestión de riesgo y tamaño de posición automático.
- Monitorización y logging de operaciones.

## Licencia

Proyecto educativo / experimental. No se recomienda usar con dinero real sin pruebas exhaustivas.
