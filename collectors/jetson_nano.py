"""
Jetson Nano collector for NVIDIA Jetson Nano devices.
Implements Nano-specific metric parsing from tegrastats.

Example tegrastats output:
RAM 1409/3964MB (lfb 28x4MB) SWAP 0/1982MB (cached 0MB) IRAM 0/252kB(lfb 252kB)
CPU [22%@518,67%@518,off,off] EMC_FREQ 0%@1600 GR3D_FREQ 0%@76 APE 25
PLL@28.5C CPU@32C PMIC@50C GPU@30.5C AO@39.5C thermal@31.25C
POM_5V_IN 2003/2003 POM_5V_GPU 0/0 POM_5V_CPU 320/320
"""
import re
from typing import Dict
from .jetson import JetsonCollector


class JetsonNanoCollector(JetsonCollector):
    """
    Collector for NVIDIA Jetson Nano devices.

    Nano-specific characteristics:
    - 4 CPU cores (2 active + 2 off in typical load)
    - Power rails: POM_5V_IN, POM_5V_GPU, POM_5V_CPU (no mW suffix, raw values)
    - Temperature sensors: PLL, CPU, PMIC, GPU, AO, thermal
    - GPU: Single frequency without brackets (GR3D_FREQ 0%@76)
    - IRAM: Internal RAM metric (unique to Nano)
    - SWAP: Includes cached info like Xavier
    """

    def _parse_all_metrics(self, output: str) -> Dict[str, float]:
        """
        Parse tegrastats output for Jetson Nano devices.

        Nano-specific format:
        - Power rails: POM_5V_IN 2003/2003 (raw values, not mW - need to convert)
        - Temperature sensors: PLL, CPU, PMIC, GPU, AO, thermal
        - CPU: 4 cores typical
        - GPU: Single frequency WITHOUT brackets (GR3D_FREQ 0%@76)
        - IRAM: Internal RAM in kB (IRAM 0/252kB)
        - SWAP: Includes (cached XMB) suffix

        Args:
            output: Raw tegrastats output line

        Returns:
            Dictionary with metric_name -> value (normalized to standard units)
        """
        metrics = {}

        # 1. Power rails: POM_5V_IN 2003/2003 (NOT mW format!)
        #    Nano uses POM (Power Optimization Module) rails
        #    Values appear to be in mW already based on typical readings
        power_pattern = r'(POM_\w+)\s+(\d+)(?:/(\d+))?'
        for match in re.finditer(power_pattern, output):
            rail_name = match.group(1)
            current_mw = float(match.group(2))
            avg_mw = float(match.group(3)) if match.group(3) else current_mw

            # Convert to watts
            metrics[f"jetson_power_{rail_name.lower()}_watts"] = round(current_mw / 1000.0, 3)
            if match.group(3):
                metrics[f"jetson_power_{rail_name.lower()}_avg_watts"] = round(avg_mw / 1000.0, 3)

        # 2. Temperatures: PLL@28.5C, CPU@32C, thermal@31.25C, etc
        #    Nano has different sensors than Orin/Xavier
        temp_pattern = r'(\w+)@([-\d.]+)C'
        for match in re.finditer(temp_pattern, output):
            sensor_name = match.group(1)
            temp_c = float(match.group(2))

            # Skip invalid temperatures
            if temp_c < -100:
                continue

            metrics[f"jetson_temp_{sensor_name.lower()}_celsius"] = round(temp_c, 2)

        # 3. RAM: RAM 1409/3964MB
        ram_match = re.search(r'RAM\s+(\d+)/(\d+)MB', output)
        if ram_match:
            used_mb = float(ram_match.group(1))
            total_mb = float(ram_match.group(2))
            metrics["jetson_ram_used_mb"] = used_mb
            metrics["jetson_ram_total_mb"] = total_mb
            metrics["jetson_ram_used_percent"] = round((used_mb / total_mb) * 100, 2)

        # 4. SWAP: SWAP 0/1982MB (cached 0MB)
        #    Nano includes cached info like Xavier
        swap_match = re.search(r'SWAP\s+(\d+)/(\d+)MB(?:\s+\(cached\s+(\d+)MB\))?', output)
        if swap_match:
            used_mb = float(swap_match.group(1))
            total_mb = float(swap_match.group(2))
            metrics["jetson_swap_used_mb"] = used_mb
            metrics["jetson_swap_total_mb"] = total_mb

            # Nano-specific: cached SWAP
            if swap_match.group(3):
                cached_mb = float(swap_match.group(3))
                metrics["jetson_swap_cached_mb"] = cached_mb

        # 5. IRAM (Internal RAM): IRAM 0/252kB(lfb 252kB)
        #    Nano-specific metric
        iram_match = re.search(r'IRAM\s+(\d+)/(\d+)kB', output)
        if iram_match:
            used_kb = float(iram_match.group(1))
            total_kb = float(iram_match.group(2))
            metrics["jetson_iram_used_kb"] = used_kb
            metrics["jetson_iram_total_kb"] = total_kb
            metrics["jetson_iram_used_percent"] = round((used_kb / total_kb) * 100, 2) if total_kb > 0 else 0

            # IRAM LFB: lfb 252kB
            iram_lfb_match = re.search(r'IRAM\s+\d+/\d+kB\(lfb\s+(\d+)kB\)', output)
            if iram_lfb_match:
                lfb_kb = float(iram_lfb_match.group(1))
                metrics["jetson_iram_lfb_kb"] = lfb_kb

        # 6. LFB (Largest Free Block): lfb 28x4MB
        lfb_match = re.search(r'lfb\s+(\d+)x(\d+)MB', output)
        if lfb_match:
            blocks = int(lfb_match.group(1))
            block_size_mb = int(lfb_match.group(2))
            metrics["jetson_lfb_blocks"] = blocks
            metrics["jetson_lfb_total_mb"] = blocks * block_size_mb

        # 7. CPU usage: CPU [22%@518,67%@518,off,off]
        #    Nano has 4 cores (2 active + 2 off in example)
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
                    # Parse: 22%@518 -> usage=22%, freq=518MHz
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

        # 8. EMC (memory controller) frequency: EMC_FREQ 0%@1600
        emc_match = re.search(r'EMC_FREQ\s+(\d+)%(?:@(\d+))?', output)
        if emc_match:
            usage = int(emc_match.group(1))
            metrics["jetson_emc_usage_percent"] = usage
            if emc_match.group(2):
                freq_mhz = int(emc_match.group(2))
                metrics["jetson_emc_freq_mhz"] = freq_mhz

        # 9. GPU frequency: GR3D_FREQ 0%@76
        #    Nano uses SINGLE frequency WITHOUT brackets
        #    Different from Xavier (GR3D_FREQ 0%@[510]) and Orin (GR3D_FREQ 0%@[611,0])
        #    Match format: number NOT followed by opening bracket
        gpu_match = re.search(r'GR3D_FREQ\s+(\d+)%@(\d+)(?!\[)', output)
        if gpu_match:
            usage = int(gpu_match.group(1))
            freq_mhz = int(gpu_match.group(2))
            metrics["jetson_gpu_usage_percent"] = usage
            metrics["jetson_gpu_freq0_mhz"] = freq_mhz

        # 10. APE (audio processing engine) frequency: APE 25
        ape_match = re.search(r'APE\s+(\d+)', output)
        if ape_match:
            metrics["jetson_ape_freq_mhz"] = int(ape_match.group(1))

        # Note: Nano does NOT have VIC_FREQ in tegrastats output

        self.logger.debug(f"Parsed {len(metrics)} Nano metrics from tegrastats")
        return metrics
