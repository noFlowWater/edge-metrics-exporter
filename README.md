# Edge Metrics Exporter

Prometheus exporter for edge device power consumption monitoring.

## Features

- ✅ **Multiple Device Support**: Jetson Orin/Xavier, Raspberry Pi, Orange Pi, LattePanda, Shelly smart plugs
- 🔄 **Dynamic Config Reload**: Update configuration without restarting the service
- 🌐 **Central Config Server**: Manage all device configurations from one place (with bidirectional sync)
- 💾 **Local Fallback**: Continue operating with local config if central server is unavailable
- 📊 **Prometheus Integration**: Standard Prometheus metrics format
- 🎯 **Selective Metrics Collection**: Choose which metrics to collect via API or config file
- 🔍 **Auto-Discovery**: Automatically discover and register new metrics
- 🔄 **Server Sync**: Changes sync automatically to central server (optional)
- 🚀 **Simple & Core**: Minimal dependencies, easy to extend

## Current Implementation Status

| Device | Status | Method |
|--------|--------|--------|
| Jetson Orin/Xavier | ✅ **Implemented** | tegrastats |
| Raspberry Pi | 💤 TODO | INA260 I2C |
| Orange Pi | 💤 TODO | sysfs |
| LattePanda | 💤 TODO | RAPL |
| Shelly Plug | 💤 TODO | HTTP API |

## Architecture

```
[Edge Device]
 ├─ Config Loader (central API + local fallback + bidirectional sync)
 ├─ Collector (device-specific power reading with auto-discovery)
 └─ Exporter
     ├─ :9100/metrics (Prometheus)
     └─ :9101 Management API
         ├─ POST /reload (Config reload trigger)
         ├─ GET  /metrics/list (List all metrics and status)
         └─ POST /metrics/enable (Enable/disable metrics)

[Central Server]
 ├─ Config Server (GET /config/{device_id}, PUT /config/{device_id})
 └─ Prometheus
```

## Quick Start

### 1. Installation

```bash
cd /home/orin/ETRI/edge-metrics-exporter

# Install dependencies
pip3 install -r requirements.txt
```

### 2. Configuration

Create configuration files from templates:

```bash
# Create config.yaml from template
cp config.yaml.template config.yaml
nano config.yaml  # Edit as needed

# Create service file from template
cp edge-metrics-exporter.service.template edge-metrics-exporter.service
nano edge-metrics-exporter.service  # Edit as needed
```

Edit `config.yaml`:

```yaml
device_type: "jetson_orin"
interval: 1
port: 9100
reload_port: 9101

# Metrics configuration (true: collect, false: don't collect)
metrics:
  jetson_power_vdd_gpu_soc_watts: true
  jetson_power_vdd_cpu_cv_watts: true
  jetson_temp_cpu_celsius: true
  jetson_temp_gpu_celsius: false
```

### 3. Test Run

```bash
python3 exporter.py
```

Check metrics:
```bash
curl http://localhost:9100/metrics
```

### 4. Install as Systemd Service

**Option A: Automatic Installation**
```bash
./install.sh
```

**Option B: Manual Installation**
```bash
# Create service file from template if not already done
cp edge-metrics-exporter.service.template edge-metrics-exporter.service

# Edit the service file with your environment-specific values
# Replace placeholders: {{USER}}, {{WORKING_DIRECTORY}}, {{CONFIG_SERVER_URL}}, etc.
nano edge-metrics-exporter.service

# Copy service file
sudo cp edge-metrics-exporter.service /etc/systemd/system/

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable edge-metrics-exporter
sudo systemctl start edge-metrics-exporter

# Check status
sudo systemctl status edge-metrics-exporter

# View logs
sudo journalctl -u edge-metrics-exporter -f
```

### 5. Uninstall

**Option A: Automatic Uninstallation**
```bash
./uninstall.sh
```

**Option B: Manual Uninstallation**
```bash
# Stop and disable service
sudo systemctl stop edge-metrics-exporter
sudo systemctl disable edge-metrics-exporter

# Remove service file
sudo rm /etc/systemd/system/edge-metrics-exporter.service
sudo systemctl daemon-reload
```

## Configuration

### Template Files

The repository includes template files for easy deployment:

- `config.yaml.template`: Template for local configuration
- `edge-metrics-exporter.service.template`: Template for systemd service file

**Note**: The actual `config.yaml` and `*.service` files are git-ignored. Create them from templates for your environment.

### Environment Variables

Set in `edge-metrics-exporter.service`:

- `CONFIG_SERVER_URL`: Central config server URL (default: `http://localhost:8080`)
- `CONFIG_TIMEOUT`: Request timeout in seconds (default: `5`)
- `LOCAL_CONFIG_PATH`: Path to local fallback config (default: `./config.yaml`)

**Service File Template Placeholders**:
- `{{USER}}`: System user to run the service
- `{{WORKING_DIRECTORY}}`: Full path to the exporter directory
- `{{CONFIG_SERVER_URL}}`: Central config server URL
- `{{CONFIG_TIMEOUT}}`: Timeout value in seconds
- `{{LOCAL_CONFIG_PATH}}`: Path to config.yaml file

### Config File (`config.yaml`)

```yaml
device_type: "jetson_orin"  # Device type
interval: 1                  # Collection interval (seconds)
port: 9100                   # Prometheus metrics port
reload_port: 9101            # Management API port

# Metrics configuration (true: collect, false: don't collect)
# New metrics discovered automatically are added with false (disabled)
# You can enable/disable metrics via:
#   - Editing this file and reloading: POST http://localhost:9101/reload
#   - Using the API: POST http://localhost:9101/metrics/enable
metrics:
  jetson_power_vdd_gpu_soc_watts: true
  jetson_power_vdd_cpu_cv_watts: true
  jetson_temp_cpu_celsius: true
  jetson_temp_gpu_celsius: false
  jetson_ram_used_percent: true
```

**Note:** The old `enabled_metrics` list format is automatically converted to the new `metrics` dict format for backward compatibility.

## Usage

### Prometheus Configuration

Add to Prometheus `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'edge-power'
    static_configs:
      - targets:
          - 'edge-01:9100'
          - 'edge-02:9100'
    scrape_interval: 5s
```

### Example Queries

```promql
# Total power consumption by device
power_total_watts{device_type="jetson_orin"}

# GPU power consumption
power_gpu_watts{hostname="edge-01"}

# Sum of all devices
sum(power_total_watts)

# Average power over 5 minutes
avg_over_time(power_total_watts[5m])
```

### Management API

#### List All Metrics

View all available metrics and their enabled/disabled status:

```bash
curl http://localhost:9101/metrics/list
```

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

#### Enable/Disable Metrics

Dynamically enable or disable specific metrics without restarting:

```bash
curl -X POST http://localhost:9101/metrics/enable \
  -H "Content-Type: application/json" \
  -d '{
    "jetson_gpu_usage_percent": true,
    "jetson_cpu_avg_usage_percent": true
  }'
```

**Response:**
```json
{
  "status": "success",
  "updated": 2,
  "metrics": {
    "jetson_gpu_usage_percent": true,
    "jetson_cpu_avg_usage_percent": true
  }
}
```

**What happens:**
1. Metrics configuration is immediately saved to `config.yaml`
2. Changes sync to Config Server (if available, non-blocking)
3. Metrics are exposed in Prometheus from the next collection cycle

#### Config Reload

Trigger full config reload from server/file without restarting:

```bash
curl -X POST http://edge-01:9101/reload
```

## Metrics

### Auto-Discovery

The exporter **automatically discovers** all available metrics from the collector. When a new metric is detected:
1. It's automatically added to `config.yaml` with `enabled: false`
2. Changes are synced to Config Server (if available)
3. You can enable it via the API or config file

### Jetson Orin/Xavier

Example available metrics (dynamically discovered from tegrastats):

| Metric | Description | Unit |
|--------|-------------|------|
| `jetson_power_vdd_gpu_soc_watts` | GPU/SoC power consumption | Watts |
| `jetson_power_vdd_cpu_cv_watts` | CPU power consumption | Watts |
| `jetson_temp_cpu_celsius` | CPU temperature | Celsius |
| `jetson_temp_gpu_celsius` | GPU temperature | Celsius |
| `jetson_ram_used_mb` | RAM usage | MB |
| `jetson_ram_used_percent` | RAM usage | Percent |
| `jetson_cpu_avg_usage_percent` | Average CPU usage | Percent |
| `jetson_gpu_usage_percent` | GPU usage | Percent |
| `jetson_cpu_core{N}_usage_percent` | Per-core CPU usage | Percent |
| `jetson_emc_freq_mhz` | Memory controller frequency | MHz |

**Note:** Actual metrics depend on your specific Jetson device and tegrastats output.

All metrics include labels:
- `device_type`: Device type (e.g., `jetson_orin`)
- `hostname`: Device hostname

## Adding New Devices

1. Create new collector in `collectors/`:

```python
# collectors/new_device.py
from .base import BaseCollector

class NewDeviceCollector(BaseCollector):
    @classmethod
    def metric_names(cls):
        return ["power_total_watts"]

    def get_metrics(self):
        # Implement power reading logic
        return {"power_total_watts": 10.5}
```

2. Register in `collectors/__init__.py`:

```python
elif device_type == "new_device":
    from .new_device import NewDeviceCollector
    return NewDeviceCollector(config)
```

3. Update config:

```yaml
device_type: "new_device"
```

## Troubleshooting

### Service not starting

```bash
# Check logs
sudo journalctl -u edge-metrics-exporter -n 50

# Test manually
cd /home/orin/ETRI/edge-metrics-exporter
python3 exporter.py
```

### tegrastats not found (Jetson)

Ensure you're on a Jetson device and tegrastats is available:

```bash
which tegrastats
# Should return: /usr/bin/tegrastats
```

### Config server unreachable

The exporter will automatically fall back to local `config.yaml`. Check logs:

```bash
sudo journalctl -u edge-metrics-exporter | grep "fallback"
```

## Development

### Running Tests

```bash
# Test Jetson collector
python3 -c "
from collectors import get_collector
collector = get_collector('jetson_orin', {})
print(collector.get_metrics())
"
```

### Debugging

Enable debug logging in `exporter.py`:

```python
logging.basicConfig(level=logging.DEBUG)
```

## TODO

### Collectors
- [ ] Implement Raspberry Pi collector (INA260)
- [ ] Implement Orange Pi collector (sysfs)
- [ ] Implement LattePanda collector (RAPL)
- [ ] Implement Shelly collector (HTTP API)

### Infrastructure
- [ ] Create central Config Server (implement PUT /config/{device_id})
- [ ] Add Grafana dashboard templates
- [ ] Add alert rules for Prometheus

### Completed ✅
- [x] Selective metrics collection (metrics dict format)
- [x] Auto-discovery of new metrics
- [x] Management API (GET /metrics/list, POST /metrics/enable)
- [x] Bidirectional server sync (client → server)
- [x] Thread-safe config updates
- [x] Backward compatibility (enabled_metrics list → metrics dict)

## License

MIT License

## Contributing

PRs welcome! Please ensure:
- Code follows existing style
- Add tests for new collectors
- Update README with new features
