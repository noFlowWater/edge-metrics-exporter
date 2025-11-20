"""
Jetson collector base class for NVIDIA Jetson devices (Orin, Xavier, etc).
Uses tegrastats to read all available metrics dynamically.
"""
import subprocess
from typing import Dict, List
from .base import BaseCollector


class JetsonCollector(BaseCollector):
    """
    Base collector for NVIDIA Jetson devices.
    Provides common tegrastats execution logic.
    Subclasses must implement _parse_all_metrics() for device-specific parsing.
    """

    # Cache for discovered metrics (updated on each run)
    _cached_metric_names = []

    @classmethod
    def metric_names(cls) -> List[str]:
        """
        Return list of available metrics.
        Returns cached list or default list if not yet discovered.
        """
        if cls._cached_metric_names:
            return cls._cached_metric_names

        # Default return until first collection
        return ["jetson_metric_discovered_on_first_run"]

    def get_metrics(self) -> Dict[str, float]:
        """
        Collect ALL metrics from tegrastats dynamically.

        Tegrastats output example:
        RAM 5848/62801MB CPU [0%@1728,...] EMC_FREQ 0%@3199 VDD_GPU_SOC 3176mW/3176mW ...

        Returns:
            Dictionary with all metrics in standardized units (watts, celsius, percent, MB, MHz)
        """
        process = None
        try:
            # Start tegrastats and capture stdout
            # tegrastats runs continuously, so we read one line and terminate
            # Use sudo only if not running as root
            import os
            cmd = ["tegrastats", "--interval", "100"]
            if os.geteuid() != 0:  # Not root
                cmd.insert(0, "sudo")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )

            # Read first line (blocks until available, typically ~100ms)
            output = process.stdout.readline().strip()

            if not output:
                raise RuntimeError("tegrastats returned empty output")

            # Parse ALL metrics
            metrics = self._parse_all_metrics(output)

            # Update cached metric names
            JetsonCollector._cached_metric_names = sorted(metrics.keys())

            return metrics

        except FileNotFoundError:
            self.logger.error("tegrastats command not found - is this a Jetson device?")
            raise RuntimeError("tegrastats not found")
        except Exception as e:
            self.logger.error(f"Failed to collect Jetson metrics: {e}")
            raise
        finally:
            # Cleanup: close pipes and terminate process
            if process:
                try:
                    # Close pipes first to prevent file handle leaks
                    if process.stdout:
                        process.stdout.close()
                    if process.stderr:
                        process.stderr.close()

                    process.terminate()
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                except Exception as e:
                    self.logger.debug(f"Process cleanup warning: {e}")

    def _parse_all_metrics(self, output: str) -> Dict[str, float]:
        """
        Parse tegrastats output to extract ALL metrics dynamically.
        Must be implemented by device-specific subclasses.

        Args:
            output: Raw tegrastats output line

        Returns:
            Dictionary with metric_name -> value (normalized to standard units)
        """
        raise NotImplementedError("Subclasses must implement _parse_all_metrics()")
