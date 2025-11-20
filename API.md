# Edge Metrics Exporter API Documentation

## Device Types and Collectors

### Jetson Devices

The exporter supports multiple Jetson device types with device-specific metric parsing:

| Device Type | Config Value | Collector Class | Description |
|-------------|--------------|-----------------|-------------|
| Jetson Orin | `jetson_orin` | `JetsonOrinCollector` | NVIDIA Jetson Orin devices |
| Jetson Xavier | `jetson_xavier` | `JetsonXavierCollector` | NVIDIA Jetson Xavier devices |
| Jetson Nano | `jetson_nano` | `JetsonNanoCollector` | NVIDIA Jetson Nano devices |
| Generic Jetson | `jetson` | `JetsonOrinCollector` (fallback) | Generic fallback, uses Orin parsing |

#### Architecture

All Jetson collectors inherit from the base `JetsonCollector` class:

```
JetsonCollector (Base)
  ├─ get_metrics()           # Common tegrastats execution
  ├─ metric_names()          # Common metric caching
  └─ _parse_all_metrics()    # Abstract - implemented by subclasses

JetsonOrinCollector(JetsonCollector)
  └─ _parse_all_metrics()    # Orin-specific parsing

JetsonXavierCollector(JetsonCollector)
  └─ _parse_all_metrics()    # Xavier-specific parsing

JetsonNanoCollector(JetsonCollector)
  └─ _parse_all_metrics()    # Nano-specific parsing
```

**Implementation:**
- [collectors/jetson.py](collectors/jetson.py) - Base class with common tegrastats execution
- [collectors/jetson_orin.py](collectors/jetson_orin.py) - Orin-specific parsing
- [collectors/jetson_xavier.py](collectors/jetson_xavier.py) - Xavier-specific parsing
- [collectors/jetson_nano.py](collectors/jetson_nano.py) - Nano-specific parsing
- [collectors/__init__.py](collectors/__init__.py) - Factory pattern for collector selection

#### Device-Specific Differences

##### Jetson Orin
- **CPU Cores:** 8 cores (typical for Orin)
- **Power Rails:** VDD_GPU_SOC, VDD_CPU_CV, VDDQ_VDD2_1V8AO, VIN_SYS_5V0
- **Temperature Sensors:** CPU, GPU, SOC0, SOC1, SOC2, TBOARD, TDIODE, TJ
- **GPU:** 2 frequency clusters
- **File:** [collectors/jetson_orin.py](collectors/jetson_orin.py)

##### Jetson Xavier
- **CPU Cores:** 6 cores (typically 4 active + 2 off)
- **Power Rails:** VDD_IN, VDD_CPU_GPU_CV, VDD_SOC
- **Temperature Sensors:** AUX, CPU, AO, GPU, PMIC
- **GPU:** Single frequency cluster (GR3D_FREQ 0%@[510])
- **SWAP:** Includes cached memory info (SWAP 479/3427MB (cached 3MB))
- **File:** [collectors/jetson_xavier.py](collectors/jetson_xavier.py)

**Example tegrastats output:**
```
RAM 2690/6854MB (lfb 6x1MB) SWAP 479/3427MB (cached 3MB)
CPU [3%@1904,7%@1906,1%@1905,0%@1907,off,off]
EMC_FREQ 0%@1600 GR3D_FREQ 0%@[510] VIC_FREQ 601 APE 150
AUX@39C CPU@39.5C AO@37.5C GPU@37.5C PMIC@50C
VDD_IN 5079mW/5079mW VDD_CPU_GPU_CV 696mW/696mW VDD_SOC 1104mW/1104mW
```

##### Jetson Nano
- **CPU Cores:** 4 cores (typically 2 active + 2 off)
- **Power Rails:** POM_5V_IN, POM_5V_GPU, POM_5V_CPU (Power Optimization Module)
- **Temperature Sensors:** PLL, CPU, PMIC, GPU, AO, thermal
- **GPU:** Single frequency WITHOUT brackets (GR3D_FREQ 0%@76)
- **IRAM:** Internal RAM metric (unique to Nano)
- **SWAP:** Includes cached memory info
- **File:** [collectors/jetson_nano.py](collectors/jetson_nano.py)

**Example tegrastats output:**
```
RAM 1409/3964MB (lfb 28x4MB) SWAP 0/1982MB (cached 0MB) IRAM 0/252kB(lfb 252kB)
CPU [22%@518,67%@518,off,off] EMC_FREQ 0%@1600 GR3D_FREQ 0%@76 APE 25
PLL@28.5C CPU@32C PMIC@50C GPU@30.5C AO@39.5C thermal@31.25C
POM_5V_IN 2003/2003 POM_5V_GPU 0/0 POM_5V_CPU 320/320
```

#### Configuration

```yaml
# config.yaml
device_type: jetson_orin    # or jetson_xavier, jetson_nano, or jetson
interval: 1
port: 9100
reload_port: 9101

metrics:
  jetson_power_vdd_gpu_soc_watts: true
  jetson_power_vdd_cpu_cv_watts: true
  jetson_temp_cpu_celsius: true
  jetson_temp_gpu_celsius: false
  # ... more metrics
```

## Metrics

### Common Jetson Metrics

All Jetson devices (Orin and Xavier) support these metric categories:

#### Power Metrics
| Metric Pattern | Description | Unit | Example |
|----------------|-------------|------|---------|
| `jetson_power_{rail}_watts` | Current power consumption | Watts | `jetson_power_vdd_gpu_soc_watts` |
| `jetson_power_{rail}_avg_watts` | Average power consumption | Watts | `jetson_power_vdd_cpu_cv_avg_watts` |

**Orin Rails:** `vdd_gpu_soc`, `vdd_cpu_cv`, `vddq_vdd2_1v8ao`, `vin_sys_5v0`
**Xavier Rails:** `vdd_in`, `vdd_cpu_gpu_cv`, `vdd_soc`
**Nano Rails:** `pom_5v_in`, `pom_5v_gpu`, `pom_5v_cpu`

#### Temperature Metrics
| Metric Pattern | Description | Unit | Example |
|----------------|-------------|------|---------|
| `jetson_temp_{sensor}_celsius` | Temperature reading | Celsius | `jetson_temp_cpu_celsius` |

**Orin Sensors:** `cpu`, `gpu`, `soc0`, `soc1`, `soc2`, `tboard`, `tdiode`, `tj`
**Xavier Sensors:** `aux`, `cpu`, `ao`, `gpu`, `pmic`
**Nano Sensors:** `pll`, `cpu`, `pmic`, `gpu`, `ao`, `thermal`

#### Memory Metrics
| Metric | Description | Unit |
|--------|-------------|------|
| `jetson_ram_used_mb` | RAM usage | MB |
| `jetson_ram_total_mb` | Total RAM | MB |
| `jetson_ram_used_percent` | RAM usage | Percent |
| `jetson_swap_used_mb` | SWAP usage | MB |
| `jetson_swap_total_mb` | Total SWAP | MB |
| `jetson_swap_cached_mb` | Cached SWAP (Xavier/Nano) | MB |
| `jetson_lfb_blocks` | Largest free block count | Count |
| `jetson_lfb_total_mb` | Total LFB size | MB |
| `jetson_iram_used_kb` | Internal RAM usage (Nano only) | KB |
| `jetson_iram_total_kb` | Total internal RAM (Nano only) | KB |
| `jetson_iram_used_percent` | Internal RAM usage (Nano only) | Percent |
| `jetson_iram_lfb_kb` | Internal RAM LFB (Nano only) | KB |

#### CPU Metrics
| Metric Pattern | Description | Unit | Notes |
|----------------|-------------|------|-------|
| `jetson_cpu_core{N}_usage_percent` | Per-core CPU usage | Percent | N=0-7 for Orin |
| `jetson_cpu_core{N}_freq_mhz` | Per-core frequency | MHz | N=0-7 for Orin |
| `jetson_cpu_core{N}_status` | Core on/off status | 0 or 1 | 1=on, 0=off |
| `jetson_cpu_avg_usage_percent` | Average CPU usage | Percent | Across active cores |
| `jetson_cpu_active_cores` | Number of active cores | Count | |

**Orin:** 8 cores (core0-core7)
**Xavier:** 6 cores (core0-core5, typically 4 active + 2 off)
**Nano:** 4 cores (core0-core3, typically 2 active + 2 off)

#### GPU Metrics
| Metric | Description | Unit | Notes |
|--------|-------------|------|-------|
| `jetson_gpu_usage_percent` | GPU usage | Percent | |
| `jetson_gpu_freq{N}_mhz` | GPU frequency | MHz | N=0-1 for Orin |

**Orin:** 2 GPU frequency clusters (freq0, freq1) - GR3D_FREQ 0%@[611,0]
**Xavier:** 1 GPU frequency cluster (freq0) in brackets - GR3D_FREQ 0%@[510]
**Nano:** 1 GPU frequency (freq0) WITHOUT brackets - GR3D_FREQ 0%@76

#### Other Metrics
| Metric | Description | Unit |
|--------|-------------|------|
| `jetson_emc_usage_percent` | Memory controller usage | Percent |
| `jetson_emc_freq_mhz` | Memory controller frequency | MHz |
| `jetson_vic_freq_mhz` | Video compositor frequency (Orin/Xavier only) | MHz |
| `jetson_ape_freq_mhz` | Audio engine frequency | MHz |

### Metric Labels

All metrics include these labels:
- `device_type`: Device type (e.g., `jetson_orin`, `jetson_xavier`)
- `hostname`: Device hostname

## Management API

Base URL: `http://localhost:9101`

### Health Check

#### `GET /health`

Check exporter health and status.

**Response:**
```json
{
  "status": "healthy",
  "device_type": "jetson_orin",
  "collector": "JetsonOrinCollector",
  "metrics_count": 45,
  "config_source": "local"
}
```

### Metrics Management

#### `GET /metrics/list`

List all available metrics and their enabled/disabled status.

**Response:**
```json
{
  "metrics": {
    "jetson_power_vdd_gpu_soc_watts": true,
    "jetson_power_vdd_cpu_cv_watts": true,
    "jetson_temp_cpu_celsius": true,
    "jetson_temp_gpu_celsius": false,
    "jetson_ram_used_percent": true
  },
  "device_type": "jetson_orin",
  "source": "local"
}
```

#### `POST /metrics/enable`

Enable or disable specific metrics.

**Request:**
```json
{
  "jetson_gpu_usage_percent": true,
  "jetson_cpu_avg_usage_percent": true,
  "jetson_temp_gpu_celsius": false
}
```

**Response:**
```json
{
  "status": "success",
  "updated": 3,
  "metrics": {
    "jetson_gpu_usage_percent": true,
    "jetson_cpu_avg_usage_percent": true,
    "jetson_temp_gpu_celsius": false
  }
}
```

**Behavior:**
1. Metrics configuration is saved to `config.yaml`
2. Changes sync to Config Server (if available, non-blocking)
3. Metrics exposed in Prometheus from next collection cycle

### Configuration Management

#### `POST /reload`

Reload configuration from server or local file.

**Response:**
```json
{
  "status": "success",
  "source": "local",
  "metrics_count": 45
}
```

## Prometheus Metrics Endpoint

### `GET /metrics`

Base URL: `http://localhost:9100/metrics`

Returns metrics in Prometheus text format.

**Example Output:**
```
# HELP jetson_power_vdd_gpu_soc_watts GPU/SoC power consumption
# TYPE jetson_power_vdd_gpu_soc_watts gauge
jetson_power_vdd_gpu_soc_watts{device_type="jetson_orin",hostname="edge-01"} 3.176

# HELP jetson_temp_cpu_celsius CPU temperature
# TYPE jetson_temp_cpu_celsius gauge
jetson_temp_cpu_celsius{device_type="jetson_orin",hostname="edge-01"} 45.25

# HELP jetson_cpu_core0_usage_percent CPU core 0 usage
# TYPE jetson_cpu_core0_usage_percent gauge
jetson_cpu_core0_usage_percent{device_type="jetson_orin",hostname="edge-01"} 15.0
```

## Examples

### Configure for Jetson Orin

```yaml
# config.yaml
device_type: jetson_orin
interval: 1
port: 9100
reload_port: 9101

metrics:
  jetson_power_vdd_gpu_soc_watts: true
  jetson_power_vdd_cpu_cv_watts: true
  jetson_temp_cpu_celsius: true
  jetson_cpu_avg_usage_percent: true
```

### Configure for Jetson Xavier

```yaml
# config.yaml
device_type: jetson_xavier
interval: 1
port: 9100
reload_port: 9101

metrics:
  jetson_power_vdd_in_watts: true              # Xavier-specific rail
  jetson_power_vdd_cpu_gpu_cv_watts: true      # Xavier-specific rail
  jetson_power_vdd_soc_watts: true             # Xavier-specific rail
  jetson_temp_cpu_celsius: true
  jetson_temp_aux_celsius: true                # Xavier-specific sensor
  jetson_cpu_avg_usage_percent: true
  jetson_swap_cached_mb: true                  # Xavier-specific
```

### Configure for Jetson Nano

```yaml
# config.yaml
device_type: jetson_nano
interval: 1
port: 9100
reload_port: 9101

metrics:
  jetson_power_pom_5v_in_watts: true           # Nano-specific rail
  jetson_power_pom_5v_cpu_watts: true          # Nano-specific rail
  jetson_power_pom_5v_gpu_watts: true          # Nano-specific rail
  jetson_temp_cpu_celsius: true
  jetson_temp_thermal_celsius: true            # Nano-specific sensor
  jetson_cpu_avg_usage_percent: true
  jetson_iram_used_percent: true               # Nano-specific (Internal RAM)
  jetson_swap_cached_mb: true                  # Nano-specific
```

### Query Metrics via API

```bash
# List all metrics
curl http://localhost:9101/metrics/list

# Enable GPU metrics
curl -X POST http://localhost:9101/metrics/enable \
  -H "Content-Type: application/json" \
  -d '{"jetson_gpu_usage_percent": true}'

# Reload config
curl -X POST http://localhost:9101/reload

# Get Prometheus metrics
curl http://localhost:9100/metrics
```

### Prometheus Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'jetson-devices'
    static_configs:
      - targets:
          - 'orin-01:9100'    # Jetson Orin
          - 'xavier-01:9100'  # Jetson Xavier
    scrape_interval: 5s
```

### Prometheus Queries

```promql
# Total power consumption by device
jetson_power_vdd_gpu_soc_watts{device_type="jetson_orin"}

# CPU temperature across all Jetson devices
jetson_temp_cpu_celsius

# Average CPU usage on Orin devices
jetson_cpu_avg_usage_percent{device_type="jetson_orin"}

# GPU power consumption over time
rate(jetson_power_vdd_gpu_soc_watts[5m])

# Compare Orin vs Xavier power consumption
sum by (device_type) (jetson_power_vdd_gpu_soc_watts)
```

## Error Handling

### Common Errors

#### Collector Not Found
```json
{
  "error": "Unsupported device type: unknown_device"
}
```

**Solution:** Use supported device types: `jetson_orin`, `jetson_xavier`, `jetson`

#### tegrastats Not Available
```
RuntimeError: tegrastats not found
```

**Solution:** Ensure running on actual Jetson hardware with tegrastats available

#### Invalid Metric Name
```json
{
  "error": "Invalid metric name: invalid_metric"
}
```

**Solution:** Check available metrics via `GET /metrics/list`

## Implementation Notes

### Adding New Jetson Models

To add support for a new Jetson model (e.g., Jetson Nano):

1. Create new collector file:
```python
# collectors/jetson_nano.py
from .jetson import JetsonCollector

class JetsonNanoCollector(JetsonCollector):
    def _parse_all_metrics(self, output: str) -> Dict[str, float]:
        # Implement Nano-specific parsing
        pass
```

2. Register in factory:
```python
# collectors/__init__.py
elif device_type == "jetson_nano":
    from .jetson_nano import JetsonNanoCollector
    return JetsonNanoCollector(config)
```

3. Update documentation with Nano-specific metrics

### Metric Auto-Discovery

All Jetson collectors automatically discover available metrics from tegrastats output. When new metrics are detected:

1. Metrics are added to internal cache
2. Config file is updated with `enabled: false`
3. Changes sync to Config Server (if available)
4. Enable via API or config file

This allows the same codebase to work across different Jetson models with varying metric availability.
