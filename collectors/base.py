"""
Base collector abstract class for power metrics collection.
"""
from abc import ABC, abstractmethod
from typing import Dict, List
import logging


class BaseCollector(ABC):
    """
    Abstract base class for all power collectors.
    Each device-specific collector must implement get_metrics() and metric_names().
    """

    def __init__(self, config: dict):
        """
        Initialize collector with configuration.

        Args:
            config: Configuration dictionary from config loader
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def get_metrics(self) -> Dict[str, float]:
        """
        Collect all available power metrics from the device.

        Returns:
            Dictionary mapping metric names to values in watts.
            Example: {
                "power_total_watts": 15.3,
                "power_gpu_watts": 8.2,
                "power_cpu_watts": 5.1
            }

        Raises:
            Exception: If metric collection fails
        """
        pass

    @classmethod
    @abstractmethod
    def metric_names(cls) -> List[str]:
        """
        Return list of metric names this collector can provide.

        Returns:
            List of metric name strings.
            Example: ["power_total_watts", "power_gpu_watts"]
        """
        pass

    def safe_get_metrics(self) -> Dict[str, float]:
        """
        Wrapper that catches exceptions and returns empty dict on failure.
        This ensures the exporter continues running even if collection fails.

        Returns:
            Metrics dict or empty dict if collection failed
        """
        try:
            return self.get_metrics()
        except Exception as e:
            self.logger.error(f"Failed to collect metrics: {e}")
            return {}
