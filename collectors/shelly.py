"""
Shelly smart plug collector.
Fetches power metrics from shelly_server via HTTP API.
"""
import socket
from typing import Dict, List
import requests
from .base import BaseCollector


class ShellyCollector(BaseCollector):
    """
    Power collector for devices connected to Shelly smart plugs.

    This collector fetches metrics from the independent shelly_server
    which maintains WebSocket connections with Shelly plugs.

    Architecture:
    Shelly Plug → WebSocket → shelly_server → HTTP API → ShellyCollector
    """

    def __init__(self, config: dict):
        super().__init__(config)

        # Get shelly_server URL from config
        shelly_config = config.get("shelly", {})
        self.server_url = shelly_config.get("server_url", "http://localhost:8766")

        # Device ID (defaults to hostname)
        self.device_id = shelly_config.get("device_id") or socket.gethostname()

        self.logger.info(f"Shelly collector initialized")
        self.logger.info(f"  Server URL: {self.server_url}")
        self.logger.info(f"  Device ID: {self.device_id}")

    @classmethod
    def metric_names(cls) -> List[str]:
        """
        Return list of metric names this collector provides.

        Returns:
            List of metric names
        """
        return [
            "power_total_watts",      # Total power consumption (W)
            "power_voltage_volts",    # Voltage (V)
            "power_current_amps"      # Current (A)
        ]

    def get_metrics(self) -> Dict[str, float]:
        """
        Fetch power metrics from shelly_server (1:1:1 관계, device_id 불필요).

        Returns:
            Dictionary of metrics {metric_name: value}
            Returns empty dict if metrics unavailable
        """
        try:
            # HTTP GET to shelly_server (device_id 없이)
            url = f"{self.server_url}/metrics"
            response = requests.get(url, timeout=2)

            response.raise_for_status()

            # Parse JSON response
            data = response.json()
            metrics = data.get("metrics", {})

            if not metrics:
                self.logger.warning("No metrics available from shelly_server")
                return {}

            return metrics

        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout fetching Shelly metrics from {self.server_url}")
            return {}

        except requests.exceptions.ConnectionError:
            self.logger.error(f"Cannot connect to shelly_server at {self.server_url}")
            return {}

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                self.logger.warning("No Shelly device connected to server")
            else:
                self.logger.error(f"HTTP error fetching Shelly metrics: {e}")
            return {}

        except Exception as e:
            self.logger.error(f"Failed to fetch Shelly metrics: {e}")
            return {}
