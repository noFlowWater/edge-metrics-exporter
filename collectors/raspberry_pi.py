"""
Raspberry Pi collector (TODO - not yet implemented).
Will use INA260 I2C sensor or similar for power measurement.
"""
from typing import Dict, List
from .base import BaseCollector


class RaspberryPiCollector(BaseCollector):
    """
    Power collector for Raspberry Pi devices.

    TODO: Implement using INA260/INA219 I2C sensor
    - Use smbus2 library to read from I2C bus
    - Calculate power from voltage and current readings
    - Typical I2C address: 0x40 or 0x41
    """

    @classmethod
    def metric_names(cls) -> List[str]:
        return ["power_total_watts"]

    def get_metrics(self) -> Dict[str, float]:
        """
        TODO: Implement INA260 I2C reading

        Implementation steps:
        1. from smbus2 import SMBus
        2. Read voltage and current registers
        3. Calculate power: P = V * I
        4. Return {"power_total_watts": value}
        """
        raise NotImplementedError(
            "RaspberryPi collector not implemented yet. "
            "Need to implement INA260 I2C sensor reading."
        )
