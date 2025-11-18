"""
Jetson collector for NVIDIA Jetson devices (Orin, Xavier, etc).
Uses tegrastats to read all available metrics dynamically.
"""
import subprocess
import re
from typing import Dict, List
from .base import BaseCollector


class JetsonCollector(BaseCollector):
    """
    Power collector for NVIDIA Jetson devices.
    Dynamically parses ALL metrics from tegrastats output.
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
            # Cleanup: terminate process
            if process:
                try:
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

        Pattern matching:
        1. Power rails: VDD_GPU_SOC 3176mW/3176mW -> [name, value, unit]
        2. Temperatures: CPU@45.25C -> [name, value, unit]
        3. Frequencies: EMC_FREQ 0%@3199 -> [name, value, unit]
        4. RAM: RAM 5848/62801MB -> [name, used, total, unit]
        5. CPU usage: CPU [0%@1728,...] -> multiple values

        Returns:
            Dictionary with metric_name -> value (normalized to standard units)
        """
        metrics = {}

        # 1. Power rails: VDD_GPU_SOC 3176mW/3176mW or VDD_GPU_SOC 3176mW
        #    NC (not connected) rails will be skipped
        power_pattern = r'(\w+)\s+(\d+)(?:/(\d+))?mW'
        for match in re.finditer(power_pattern, output):
            rail_name = match.group(1)
            current_mw = float(match.group(2))
            avg_mw = float(match.group(3)) if match.group(3) else current_mw

            # Skip NC (not connected) rails
            if rail_name == "NC":
                continue

            # Add current and average values
            metrics[f"jetson_power_{rail_name.lower()}_watts"] = round(current_mw / 1000.0, 3)
            if match.group(3):
                metrics[f"jetson_power_{rail_name.lower()}_avg_watts"] = round(avg_mw / 1000.0, 3)

        # 2. Temperatures: CPU@45.25C, GPU@39.875C, etc
        temp_pattern = r'(\w+)@([-\d.]+)C'
        for match in re.finditer(temp_pattern, output):
            sensor_name = match.group(1)
            temp_c = float(match.group(2))

            # Skip invalid temperatures (like CV0@-256C)
            if temp_c < -100:
                continue

            metrics[f"jetson_temp_{sensor_name.lower()}_celsius"] = round(temp_c, 2)

        # 3. RAM: RAM 5848/62801MB
        ram_match = re.search(r'RAM\s+(\d+)/(\d+)MB', output)
        if ram_match:
            used_mb = float(ram_match.group(1))
            total_mb = float(ram_match.group(2))
            metrics["jetson_ram_used_mb"] = used_mb
            metrics["jetson_ram_total_mb"] = total_mb
            metrics["jetson_ram_used_percent"] = round((used_mb / total_mb) * 100, 2)

        # 4. SWAP: SWAP 0/31400MB
        swap_match = re.search(r'SWAP\s+(\d+)/(\d+)MB', output)
        if swap_match:
            used_mb = float(swap_match.group(1))
            total_mb = float(swap_match.group(2))
            metrics["jetson_swap_used_mb"] = used_mb
            metrics["jetson_swap_total_mb"] = total_mb

        # 5. LFB (Largest Free Block): lfb 5875x4MB
        lfb_match = re.search(r'lfb\s+(\d+)x(\d+)MB', output)
        if lfb_match:
            blocks = int(lfb_match.group(1))
            block_size_mb = int(lfb_match.group(2))
            metrics["jetson_lfb_blocks"] = blocks
            metrics["jetson_lfb_total_mb"] = blocks * block_size_mb

        # 6. CPU usage: CPU [0%@1728,1%@1728,...]
        cpu_match = re.search(r'CPU\s+\[([^\]]+)\]', output)
        if cpu_match:
            cpu_data = cpu_match.group(1)
            cpu_cores = cpu_data.split(',')

            total_usage = 0
            active_cores = 0

            for i, core in enumerate(cpu_cores):
                core = core.strip()
                if core == "off":
                    metrics[f"jetson_cpu_core{i}_status"] = 0  # off
                else:
                    # Parse: 0%@1728 -> usage=0%, freq=1728MHz
                    core_match = re.match(r'(\d+)%@(\d+)', core)
                    if core_match:
                        usage = int(core_match.group(1))
                        freq_mhz = int(core_match.group(2))

                        metrics[f"jetson_cpu_core{i}_usage_percent"] = usage
                        metrics[f"jetson_cpu_core{i}_freq_mhz"] = freq_mhz
                        metrics[f"jetson_cpu_core{i}_status"] = 1  # on

                        total_usage += usage
                        active_cores += 1

            # Average CPU usage across active cores
            if active_cores > 0:
                metrics["jetson_cpu_avg_usage_percent"] = round(total_usage / active_cores, 2)
                metrics["jetson_cpu_active_cores"] = active_cores

        # 7. EMC (memory controller) frequency: EMC_FREQ 0%@3199
        emc_match = re.search(r'EMC_FREQ\s+(\d+)%(?:@(\d+))?', output)
        if emc_match:
            usage = int(emc_match.group(1))
            metrics["jetson_emc_usage_percent"] = usage
            if emc_match.group(2):
                freq_mhz = int(emc_match.group(2))
                metrics["jetson_emc_freq_mhz"] = freq_mhz

        # 8. GPU frequency: GR3D_FREQ 0%@[611,0]
        gpu_match = re.search(r'GR3D_FREQ\s+(\d+)%@\[([^\]]+)\]', output)
        if gpu_match:
            usage = int(gpu_match.group(1))
            freqs = gpu_match.group(2).split(',')

            metrics["jetson_gpu_usage_percent"] = usage
            for i, freq in enumerate(freqs):
                metrics[f"jetson_gpu_freq{i}_mhz"] = int(freq.strip())

        # 9. VIC (video image compositor) frequency: VIC_FREQ 729
        vic_match = re.search(r'VIC_FREQ\s+(\d+)', output)
        if vic_match:
            metrics["jetson_vic_freq_mhz"] = int(vic_match.group(1))

        # 10. APE (audio processing engine) frequency: APE 174
        ape_match = re.search(r'APE\s+(\d+)', output)
        if ape_match:
            metrics["jetson_ape_freq_mhz"] = int(ape_match.group(1))

        self.logger.debug(f"Parsed {len(metrics)} metrics from tegrastats")
        return metrics
