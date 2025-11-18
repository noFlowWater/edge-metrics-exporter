"""
Shelly smart plug collector (TODO - not yet implemented).
Will use Shelly HTTP API to read power consumption.
"""
from typing import Dict, List
from .base import BaseCollector


class ShellyCollector(BaseCollector):
    """
    Power collector for devices connected to Shelly smart plugs.

    TODO: Implement using Shelly HTTP API
    - Shelly provides REST API for power monitoring
    - Endpoint: http://<shelly_ip>/rpc/Switch.GetStatus
    - Response includes current power consumption
    """

    @classmethod
    def metric_names(cls) -> List[str]:
        return [
            "power_total_watts",
            "power_voltage_volts",   # Voltage reading
            "power_current_amps"     # Current reading
        ]

    def get_metrics(self) -> Dict[str, float]:
        """
        TODO: Implement Shelly API call

        Implementation steps:
        1. import requests
        2. GET http://{shelly_host}/rpc/Switch.GetStatus?id=0
        3. Parse JSON response: {"apower": watts, "voltage": volts, "current": amps}
        4. Return metrics dict

        Configuration example:
        {
            "device_type": "shelly",
            "shelly": {
                "host": "192.168.1.100",
                "switch_id": 0
            }
        }
        """
        raise NotImplementedError(
            "Shelly collector not implemented yet. "
            "Need to implement Shelly HTTP API call."
        )
