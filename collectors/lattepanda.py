"""
LattePanda collector (TODO - not yet implemented).
Will use RAPL (Running Average Power Limit) for Intel CPUs.
"""
from typing import Dict, List
from .base import BaseCollector


class LattePandaCollector(BaseCollector):
    """
    Power collector for LattePanda devices (Intel CPU).

    TODO: Implement using RAPL (Running Average Power Limit)
    - Read from /sys/class/powercap/intel-rapl/
    - RAPL provides power readings for Intel CPUs
    - Available on Intel Sandy Bridge and later
    """

    @classmethod
    def metric_names(cls) -> List[str]:
        return [
            "power_total_watts",
            "power_package_watts",  # CPU package power
            "power_dram_watts"      # DRAM power
        ]

    def get_metrics(self) -> Dict[str, float]:
        """
        TODO: Implement RAPL reading

        Implementation steps:
        1. Read from /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj
        2. Calculate power from energy delta over time interval
        3. P = ΔE / Δt
        4. Return power metrics in watts
        """
        raise NotImplementedError(
            "LattePanda collector not implemented yet. "
            "Need to implement RAPL (Intel RAPL) reading."
        )
