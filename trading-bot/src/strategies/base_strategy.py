from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """Clase base para estrategias de trading."""

    @abstractmethod
    def generate_signals(self, data):
        """
        A partir de los datos (DataFrame), devuelve señales de trading:
        1 = compra, -1 = venta, 0 = nada.
        """
        pass
