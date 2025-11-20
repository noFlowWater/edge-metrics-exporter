"""
Collector factory for dynamically loading device-specific collectors.
"""
from typing import Dict
from .base import BaseCollector


def get_collector(device_type: str, config: Dict) -> BaseCollector:
    """
    Factory function to get the appropriate collector for a device type.

    Args:
        device_type: Type of device (e.g., "jetson_orin", "raspberry_pi")
        config: Configuration dictionary

    Returns:
        Initialized collector instance

    Raises:
        ValueError: If device_type is not supported
    """
    device_type = device_type.lower()

    if device_type == "jetson_orin":
        from .jetson_orin import JetsonOrinCollector
        return JetsonOrinCollector(config)

    elif device_type == "jetson_xavier":
        from .jetson_xavier import JetsonXavierCollector
        return JetsonXavierCollector(config)

    elif device_type == "jetson_nano":
        from .jetson_nano import JetsonNanoCollector
        return JetsonNanoCollector(config)

    elif device_type == "jetson":
        # Generic fallback - defaults to Orin
        from .jetson_orin import JetsonOrinCollector
        return JetsonOrinCollector(config)

    elif device_type == "raspberry_pi":
        from .raspberry_pi import RaspberryPiCollector
        return RaspberryPiCollector(config)

    elif device_type == "orange_pi":
        from .orange_pi import OrangePiCollector
        return OrangePiCollector(config)

    elif device_type == "lattepanda":
        from .lattepanda import LattePandaCollector
        return LattePandaCollector(config)

    elif device_type == "shelly":
        from .shelly import ShellyCollector
        return ShellyCollector(config)

    else:
        raise ValueError(
            f"Unsupported device type: {device_type}. "
            f"Supported types: jetson_orin, jetson_xavier, jetson_nano, raspberry_pi, "
            f"orange_pi, lattepanda, shelly"
        )


__all__ = ["BaseCollector", "get_collector"]
