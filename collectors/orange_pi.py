"""
Orange Pi collector (TODO - not yet implemented).
Will use sysfs or similar for power measurement.
"""
from typing import Dict, List
from .base import BaseCollector


class OrangePiCollector(BaseCollector):
    """
    Power collector for Orange Pi devices.

    TODO: Implement using sysfs readings
    - Check /sys/class/power_supply/ for power metrics
    - Or use INA260 sensor similar to Raspberry Pi
    """

    @classmethod
    def metric_names(cls) -> List[str]:
        return ["power_total_watts"]

    def get_metrics(self) -> Dict[str, float]:
        """
        TODO: Implement sysfs or sensor reading

        Implementation options:
        1. Read from /sys/class/power_supply/*/power_now
        2. Use INA260 I2C sensor (similar to RPi)
        3. Use device-specific power monitoring tools
        """
        raise NotImplementedError(
            "OrangePi collector not implemented yet. "
            "Need to implement sysfs or sensor reading."
        )
