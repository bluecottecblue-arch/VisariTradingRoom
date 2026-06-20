"""
Interfaccia base per i provider di dati di mercato.

Per aggiungere un nuovo provider:
1. Crea un file in providers/nome_provider.py
2. Estendi DataProviderBase
3. Implementa fetch_ohlcv()
4. Registralo in PROVIDER_REGISTRY
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd


class DataProviderBase(ABC):
    """Base class per tutti i provider di dati di mercato."""

    name: str = "base"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """
        Scarica dati OHLCV per il simbolo e il periodo specificati.

        :param symbol: ticker o simbolo (es. EURUSD, AAPL)
        :param timeframe: granularità (es. 1d, 1h, 1m)
        :param start: data inizio ISO (YYYY-MM-DD)
        :param end: data fine ISO (YYYY-MM-DD)
        :return: DataFrame con colonne timestamp, open, high, low, close, volume
        """
        ...

    def _validate_dates(self, start: str, end: str) -> None:
        import pandas as pd
        s = pd.Timestamp(start)
        e = pd.Timestamp(end)
        if s >= e:
            raise ValueError(f"La data di inizio ({start}) deve essere precedente a quella di fine ({end}).")


# ---- Registry ----

def _load_providers() -> dict:
    """Importazione lazy per evitare errori se alcuni provider non sono installati."""
    registry: dict = {}
    try:
        from .providers.polygon_provider import PolygonProvider
        registry["polygon"] = PolygonProvider
    except ImportError:
        pass
    try:
        from .providers.twelve_data_provider import TwelveDataProvider
        registry["twelve_data"] = TwelveDataProvider
    except ImportError:
        pass
    try:
        from .providers.stooq_provider import StooqProvider
        registry["stooq"] = StooqProvider
    except ImportError:
        pass
    try:
        from .providers.yfinance_provider import YfinanceProvider
        registry["yfinance"] = YfinanceProvider
    except ImportError:
        pass
    try:
        from .providers.alpha_vantage_provider import AlphaVantageProvider
        registry["alpha_vantage"] = AlphaVantageProvider
    except ImportError:
        pass
    return registry


def get_provider(provider_name: str, api_key: Optional[str] = None) -> DataProviderBase:
    """Restituisce l'istanza del provider richiesto."""
    registry = _load_providers()
    cls = registry.get(provider_name.lower())
    if cls is None:
        available = list(registry.keys())
        raise ValueError(
            f"Provider '{provider_name}' non trovato. "
            f"Disponibili: {available}"
        )
    return cls(api_key=api_key)


def list_providers() -> list[dict]:
    """Restituisce i metadati dei provider disponibili."""
    registry = _load_providers()
    return [
        {"name": name, "class": cls.__name__}
        for name, cls in registry.items()
    ]
