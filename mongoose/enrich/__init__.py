from abc import ABC, abstractmethod
from typing import Any


class AbstractEnricher(ABC):
    @abstractmethod
    def enrich_alert(self, alert_data: Any) -> None:
        pass

    @abstractmethod
    def enrich_dpi(self, dpi_data: Any) -> None:
        pass
