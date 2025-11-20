"""
Jetson Xavier collector for NVIDIA Jetson Xavier devices.
Implements Xavier-specific metric parsing from tegrastats.

Example tegrastats output:
RAM 2690/6854MB (lfb 6x1MB) SWAP 479/3427MB (cached 3MB) CPU [3%@1904,7%@1906,1%@1905,0%@1907,off,off]
EMC_FREQ 0%@1600 GR3D_FREQ 0%@[510] VIC_FREQ 601 APE 150 AUX@39C CPU@39.5C AO@37.5C GPU@37.5C PMIC@50C
VDD_IN 5079mW/5079mW VDD_CPU_GPU_CV 696mW/696mW VDD_SOC 1104mW/1104mW
"""
import re
from typing import Dict
from .jetson import JetsonCollector


class JetsonXavierCollector(JetsonCollector):
    """
    Collector for NVIDIA Jetson Xavier devices.

    Xavier-specific characteristics:
    - 6 CPU cores (4 active cores + 2 off in typical config)
    - Power rails: VDD_IN, VDD_CPU_GPU_CV, VDD_SOC
    - Temperature sensors: AUX, CPU, AO, GPU, PMIC
    - GPU: Single frequency cluster (GR3D_FREQ 0%@[510])
    - SWAP includes cached info: SWAP 479/3427MB (cached 3MB)
    """

    def _parse_all_metrics(self, output: str) -> Dict[str, float]:
        """
        Parse tegrastats output for Jetson Xavier devices.

        Xavier-specific format:
        - Power rails: VDD_IN, VDD_CPU_GPU_CV, VDD_SOC (vs Orin's VDD_GPU_SOC, VDD_CPU_CV)
        - Temperature sensors: AUX, CPU, AO, GPU, PMIC (vs Orin's CPU, GPU, SOC0-2, etc)
        - CPU: 6 cores typical (vs Orin's 8)
        - GPU: Single cluster GR3D_FREQ 0%@[510] (vs Orin's dual cluster [611,0])
        - SWAP: Includes (cached XMB) suffix

        Args:
            output: Raw tegrastats output line

        Returns:
            Dictionary with metric_name -> value (normalized to standard units)
        """
        metrics = {}

        # 1. Power rails: VDD_IN 6635mW/6635mW or VDD_IN 6635mW
        #    Xavier power rails: VDD_IN, VDD_CPU_GPU_CV, VDD_SOC
        #    NC (not connected) rails will be skipped
        power_pattern = r'(\w+)\s+(\d+)mW(?:/(\d+)mW)?'
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
        #    Xavier may have different sensor names
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

        # 4. SWAP: SWAP 479/3427MB (cached 3MB)
        #    Xavier includes cached info, extract it separately
        swap_match = re.search(r'SWAP\s+(\d+)/(\d+)MB(?:\s+\(cached\s+(\d+)MB\))?', output)
        if swap_match:
            used_mb = float(swap_match.group(1))
            total_mb = float(swap_match.group(2))
            metrics["jetson_swap_used_mb"] = used_mb
            metrics["jetson_swap_total_mb"] = total_mb

            # Xavier-specific: cached SWAP
            if swap_match.group(3):
                cached_mb = float(swap_match.group(3))
                metrics["jetson_swap_cached_mb"] = cached_mb

        # 5. LFB (Largest Free Block): lfb 5875x4MB
        lfb_match = re.search(r'lfb\s+(\d+)x(\d+)MB', output)
        if lfb_match:
            blocks = int(lfb_match.group(1))
            block_size_mb = int(lfb_match.group(2))
            metrics["jetson_lfb_blocks"] = blocks
            metrics["jetson_lfb_total_mb"] = blocks * block_size_mb

        # 6. CPU usage: CPU [3%@1904,7%@1906,1%@1905,0%@1907,off,off]
        #    Xavier typically has 6 cores (4 active + 2 off in example)
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
                    # Parse: 3%@1904 -> usage=3%, freq=1904MHz
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

        # 8. GPU frequency: GR3D_FREQ 0%@[510]
        #    Xavier uses single cluster in brackets: GR3D_FREQ 0%@[510]
        #    Different from Orin's dual cluster: GR3D_FREQ 0%@[611,0]
        gpu_match = re.search(r'GR3D_FREQ\s+(\d+)%@\[([^\]]+)\]', output)
        if gpu_match:
            usage = int(gpu_match.group(1))
            freqs = gpu_match.group(2).split(',')

            metrics["jetson_gpu_usage_percent"] = usage
            # Xavier typically has single frequency value
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

        self.logger.debug(f"Parsed {len(metrics)} Xavier metrics from tegrastats")
        return metrics
