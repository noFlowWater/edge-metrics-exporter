# CONFIG SERVER API Specification

> **Document Purpose:** Complete API specification for implementing a CONFIG SERVER that is 100% compatible with the edge-metrics-exporter client.
>
> **Target Audience:** Backend developers implementing the CONFIG SERVER
>
> **Status:** Production-ready specification based on actual client implementation

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [API Endpoints](#api-endpoints)
4. [Request Specifications](#request-specifications)
5. [Response Specifications](#response-specifications)
6. [Error Handling](#error-handling)
7. [Configuration Schema](#configuration-schema)
8. [Authentication & Security](#authentication--security)
9. [Client Behavior](#client-behavior)
10. [Implementation Examples](#implementation-examples)
11. [Testing Guide](#testing-guide)
12. [Code References](#code-references)

---

## Overview

### System Architecture

The edge-metrics-exporter client is a distributed metrics collection system where each edge device (Jetson Orin, Raspberry Pi, etc.) runs a metrics exporter. The CONFIG SERVER provides centralized configuration management for all devices.

```
┌─────────────────┐
│  CONFIG SERVER  │  (To be implemented)
│  Port: 8080     │
└────────┬────────┘
         │
         │ HTTP GET /config/{device_id}
         │
    ┌────┴─────────────────────────┐
    │                              │
    ▼                              ▼
┌─────────────┐            ┌─────────────┐
│  Device 1   │            │  Device 2   │
│  edge-01    │            │  edge-02    │
│  (Client)   │            │  (Client)   │
└─────────────┘            └─────────────┘
```

### Key Features

- **Single Endpoint:** Simple REST API with one GET endpoint
- **Device-Specific Config:** Each device gets custom configuration based on its hostname
- **Fallback Mechanism:** Client automatically falls back to local config if server is unavailable
- **Dynamic Reload:** Configuration can be reloaded without restarting the client
- **No Authentication:** Current implementation uses plain HTTP (suitable for internal networks)

---

## Quick Start

### Minimal Implementation

Here's the absolute minimum you need to implement:

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/config/<device_id>', methods=['GET'])
def get_config(device_id):
    # Return device-specific configuration
    return jsonify({
        "device_type": "jetson_orin",
        "interval": 1,
        "port": 9100,
        "reload_port": 9101
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

### Test It

```bash
curl http://localhost:8080/config/edge-01
```

Expected output:
```json
{
  "device_type": "jetson_orin",
  "interval": 1,
  "port": 9100,
  "reload_port": 9101
}
```

---

## API Endpoints

### GET /config/{device_id}

**Purpose:** Retrieve device-specific configuration

**URL Pattern:**
```
GET {base_url}/config/{device_id}
```

**Example:**
```
GET http://localhost:8080/config/edge-01
```

**Parameters:**

| Parameter | Type | Location | Required | Description | Example |
|-----------|------|----------|----------|-------------|---------|
| `device_id` | String | URL Path | Yes | Device hostname (automatically set by client) | `edge-01`, `jetson-orin-001` |

**Client Implementation Reference:**
- File: [config_loader.py:79-87](config_loader.py#L79-L87)

```python
url = f"{self.config_server_url}/config/{self.device_id}"
self.logger.info(f"Fetching config from {url}")

response = requests.get(url, timeout=self.timeout)
response.raise_for_status()

config = response.json()
```

### PUT /config/{device_id}

**Purpose:** Update device configuration (typically used for metrics synchronization)

**URL Pattern:**
```
PUT {base_url}/config/{device_id}
```

**Example:**
```
PUT http://localhost:8080/config/edge-01
```

**Parameters:**

| Parameter | Type | Location | Required | Description | Example |
|-----------|------|----------|----------|-------------|---------|
| `device_id` | String | URL Path | Yes | Device hostname | `edge-01`, `jetson-orin-001` |

**Request Body:**

Full configuration object (replaces existing configuration):

```json
{
  "device_type": "jetson_orin",
  "interval": 1,
  "port": 9100,
  "reload_port": 9101,
  "metrics": {
    "jetson_power_vdd_gpu_soc_watts": true,
    "jetson_power_vdd_cpu_cv_watts": true,
    "jetson_temp_cpu_celsius": false,
    "jetson_ram_used_percent": true
  }
}
```

**Response:**

Success (200 OK):
```json
{
  "status": "updated",
  "device_id": "edge-01"
}
```

Not Found (404):
```json
{
  "error": "Device not found",
  "device_id": "edge-01"
}
```

**Note:** This endpoint is optional but recommended for Phase 2 (server synchronization). If not implemented, the client will silently fail to sync and continue with local-only operation.

---

## Request Specifications

### HTTP Headers

**No special headers required.** The client sends standard HTTP GET requests.

```http
GET /config/edge-01 HTTP/1.1
Host: localhost:8080
User-Agent: python-requests/2.31.0
Accept-Encoding: gzip, deflate
Accept: */*
Connection: keep-alive
```

### Timeout Configuration

**Default Timeout:** 5 seconds

The client will abort the request if the server doesn't respond within the timeout period.

**Configuration:**
- Environment variable: `CONFIG_TIMEOUT`
- Default value: `5` (seconds)
- Client implementation: [config_loader.py:35](config_loader.py#L35)

```python
self.timeout = int(os.getenv("CONFIG_TIMEOUT", "5"))
```

**Server Requirement:** Response time must be < 5 seconds (or client's configured timeout).

### Device ID Resolution

**Device ID = Hostname**

The client automatically uses the system hostname as the device identifier:

```python
self.device_id = socket.gethostname()
```

**Examples:**
- `edge-01` → `GET /config/edge-01`
- `jetson-orin-nano` → `GET /config/jetson-orin-nano`
- `rpi-sensor-02` → `GET /config/rpi-sensor-02`

---

## Response Specifications

### Success Response (200 OK)

**Status Code:** `200`

**Content-Type:** `application/json`

**Response Body:**

```json
{
  "device_type": "jetson_orin",
  "interval": 1,
  "port": 9100,
  "reload_port": 9101,
  "enabled_metrics": [
    "jetson_power_vdd_gpu_soc_watts",
    "jetson_temp_cpu_celsius",
    "jetson_ram_used_percent"
  ]
}
```

### Required Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `device_type` | String | **YES** | - | Collector type (see [Supported Device Types](#supported-device-types)) |
| `interval` | Integer | No | `1` | Metric collection interval in seconds |
| `port` | Integer | No | `9100` | Prometheus metrics HTTP server port |
| `reload_port` | Integer | No | `9101` | Config reload trigger HTTP server port |
| `enabled_metrics` | Array[String] | No | `null` | Specific metrics to collect (null = all available) |

### Supported Device Types

**Valid values for `device_type`:**

| Device Type | Description | Collector Implementation |
|-------------|-------------|--------------------------|
| `jetson_orin` | NVIDIA Jetson Orin series | [collectors/jetson.py](collectors/jetson.py) |
| `jetson_xavier` | NVIDIA Jetson Xavier series | [collectors/jetson.py](collectors/jetson.py) |
| `jetson` | Generic NVIDIA Jetson | [collectors/jetson.py](collectors/jetson.py) |
| `raspberry_pi` | Raspberry Pi (all models) | [collectors/raspberry_pi.py](collectors/raspberry_pi.py) |
| `orange_pi` | Orange Pi boards | [collectors/orange_pi.py](collectors/orange_pi.py) |
| `lattepanda` | LattePanda boards | [collectors/lattepanda.py](collectors/lattepanda.py) |
| `shelly` | Shelly smart switches | [collectors/shelly.py](collectors/shelly.py) |

**Client Code Reference:** [collectors/__init__.py:24-42](collectors/__init__.py#L24-L42)

### Optional Configuration Fields

Different device types may accept additional configuration:

#### Shelly Devices

```json
{
  "device_type": "shelly",
  "interval": 1,
  "shelly": {
    "host": "192.168.1.100",
    "switch_id": 0
  }
}
```

#### Jetson Devices

```json
{
  "device_type": "jetson_orin",
  "interval": 1,
  "jetson": {
    "use_tegrastats": true
  }
}
```

#### INA260 Power Sensors

```json
{
  "device_type": "jetson_orin",
  "interval": 1,
  "ina260": {
    "i2c_address": "0x40"
  }
}
```

**Reference:** See [config.yaml](config.yaml) for complete examples.

---

## Error Handling

### HTTP Error Responses

The client handles errors via `response.raise_for_status()`, which throws an exception for any HTTP status code >= 400.

**Recommended Status Codes:**

| Status Code | When to Use | Example Response |
|-------------|-------------|------------------|
| `200 OK` | Device configuration found | `{"device_type": "jetson_orin", ...}` |
| `404 Not Found` | Device ID not in database | `{"error": "Device not found", "device_id": "unknown-01"}` |
| `500 Internal Server Error` | Server-side error | `{"error": "Database connection failed"}` |
| `503 Service Unavailable` | Server temporarily unavailable | `{"error": "Service temporarily unavailable"}` |

**Example 404 Response:**

```json
{
  "error": "Device not found",
  "device_id": "edge-99",
  "message": "No configuration available for this device"
}
```

### Client Fallback Behavior

**When server request fails (any error), the client will:**

1. Log a warning message
2. Attempt to load local `config.yaml` file
3. Continue operation with local configuration
4. **NOT terminate** - the exporter keeps running

**Client Implementation:** [config_loader.py:49-67](config_loader.py#L49-L67)

```python
# 1. Try central Config API
try:
    config = self._fetch_from_server()
    if config:
        self.logger.info("✅ Loaded config from central server")
        return config
except Exception as e:
    self.logger.warning(f"⚠️ Failed to fetch from central server: {e}")

# 2. Fallback: local config.yaml
try:
    config = self._load_local_config()
    self.logger.info("✅ Loaded local fallback config")
    return config
except Exception as e:
    self.logger.error(f"❌ Failed to load local config: {e}")
    raise RuntimeError("No config available")
```

### Error Scenarios

| Scenario | Client Behavior | Server Action |
|----------|-----------------|---------------|
| Device not found | Fall back to local config | Return 404 |
| Network timeout (>5s) | Fall back to local config | Optimize response time |
| Invalid JSON response | Fall back to local config | Return valid JSON |
| Missing `device_type` field | Configuration error, may crash | Always include `device_type` |
| Server down/unreachable | Fall back to local config | Ensure high availability |

---

## Configuration Schema

### Complete Configuration Object

```json
{
  "device_type": "jetson_orin",
  "interval": 1,
  "port": 9100,
  "reload_port": 9101,
  "enabled_metrics": [
    "jetson_power_vdd_gpu_soc_watts",
    "jetson_power_vdd_gpu_soc_avg_watts",
    "jetson_power_vdd_cpu_cv_watts",
    "jetson_temp_cpu_celsius",
    "jetson_temp_gpu_celsius",
    "jetson_temp_thermal_celsius",
    "jetson_ram_used_mb",
    "jetson_ram_total_mb",
    "jetson_ram_used_percent",
    "jetson_cpu_avg_usage_percent",
    "jetson_gpu_usage_percent",
    "jetson_emc_freq_mhz"
  ],
  "jetson": {
    "use_tegrastats": true
  }
}
```

### Field Descriptions

#### device_type (String, REQUIRED)

Determines which metrics collector to use.

**Validation:** Must be one of the supported device types listed in [Supported Device Types](#supported-device-types).

**Example:**
```json
"device_type": "jetson_orin"
```

#### interval (Integer, Optional)

Metric collection interval in seconds.

**Default:** `1`

**Valid Range:** Any positive integer (typically 1-60)

**Example:**
```json
"interval": 5
```

**Usage:** Client collects metrics every `interval` seconds.

#### port (Integer, Optional)

Port number for Prometheus metrics HTTP server.

**Default:** `9100`

**Valid Range:** `1024-65535` (unprivileged ports)

**Example:**
```json
"port": 9100
```

**Usage:** Prometheus scrapes `http://device:9100/metrics`

#### reload_port (Integer, Optional)

Port number for configuration reload trigger endpoint.

**Default:** `9101`

**Valid Range:** `1024-65535` (unprivileged ports)

**Example:**
```json
"reload_port": 9101
```

**Usage:** Trigger reload with `POST http://device:9101/reload`

#### enabled_metrics (Array[String], Optional)

List of specific metrics to collect.

**Default:** `null` (collect all available metrics)

**Valid Values:** Metric names depend on `device_type`

**Example:**
```json
"enabled_metrics": [
  "jetson_power_vdd_gpu_soc_watts",
  "jetson_temp_cpu_celsius"
]
```

**Jetson Metrics Examples:**
- `jetson_power_vdd_gpu_soc_watts` - GPU/SoC power consumption
- `jetson_power_vdd_cpu_cv_watts` - CPU power consumption
- `jetson_temp_cpu_celsius` - CPU temperature
- `jetson_temp_gpu_celsius` - GPU temperature
- `jetson_ram_used_mb` - RAM usage in MB
- `jetson_ram_used_percent` - RAM usage percentage
- `jetson_cpu_avg_usage_percent` - Average CPU usage
- `jetson_gpu_usage_percent` - GPU usage

**Reference:** See [collectors/jetson.py:93-226](collectors/jetson.py#L93-L226) for complete list.

---

## Authentication & Security

### Current Implementation: No Authentication

**The client does NOT implement any authentication mechanism.**

No headers, tokens, or credentials are sent with requests.

```python
# Client code - no auth headers
response = requests.get(url, timeout=self.timeout)
```

### Security Considerations

#### Recommended for Production

1. **Network Isolation**
   - Deploy CONFIG SERVER on internal network only
   - Use VPN or private network
   - Firewall rules to restrict access

2. **HTTPS (TLS)**
   - Use HTTPS instead of HTTP
   - Protect against man-in-the-middle attacks
   - Update client environment variable: `CONFIG_SERVER_URL=https://...`

3. **Future Authentication Options**
   - API key in header: `X-API-Key: secret-key`
   - Bearer token: `Authorization: Bearer <token>`
   - mTLS (mutual TLS certificates)
   - IP whitelisting

#### Current Configuration

**Default URL:** `http://localhost:8080` (localhost only)

**Environment Variable:** [edge-metrics-exporter.service:13](edge-metrics-exporter.service#L13)

```bash
Environment="CONFIG_SERVER_URL=http://localhost:8080"
```

**To use external server:**
```bash
Environment="CONFIG_SERVER_URL=http://config-server.internal:8080"
```

---

## Client Behavior

### Startup Flow

```
1. Client starts
2. ConfigLoader.load() called
3. Attempts: GET {server}/config/{hostname}
4. If success: Use server config
5. If failure: Load local config.yaml
6. Initialize metrics collector
7. Start Prometheus HTTP server
8. Start config reload HTTP server
9. Begin metrics collection loop
```

### Runtime Configuration Reload

The client supports dynamic configuration reload without restart.

**Trigger Reload:**

```bash
curl -X POST http://device-ip:9101/reload
```

**Reload Flow:**

```
1. External system: POST http://device:9101/reload
2. Client sets internal reload_flag = True
3. Main loop detects flag
4. Client calls: loader.load()
5. Attempts: GET {server}/config/{hostname}
6. If device_type changed: Reinitialize collector
7. If interval changed: Update collection frequency
8. Continue operation with new config
```

**Client Implementation:** [exporter.py:44-50,272-282](exporter.py#L44-L50)

```python
def do_POST(self):
    """Handle POST requests to /reload"""
    global reload_flag

    if self.path == '/reload':
        reload_flag = True
        logger.info("🔄 Config reload triggered via HTTP")

        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Config reload triggered\n')
```

### Configuration Validation

The client expects:

1. Valid JSON response
2. `device_type` field present
3. `device_type` value is a supported collector
4. Optional fields have correct types (integer, array, etc.)

**If validation fails:** Client will crash with an error message.

**Server responsibility:** Always return valid, well-formed configuration.

---

## Implementation Examples

### Python Flask Server

Complete working example:

```python
from flask import Flask, jsonify, abort
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Device configuration database
# In production, use a real database (PostgreSQL, MongoDB, etc.)
DEVICE_CONFIGS = {
    "edge-01": {
        "device_type": "jetson_orin",
        "interval": 1,
        "port": 9100,
        "reload_port": 9101,
        "enabled_metrics": [
            "jetson_power_vdd_gpu_soc_watts",
            "jetson_temp_cpu_celsius",
            "jetson_ram_used_percent"
        ]
    },
    "edge-02": {
        "device_type": "jetson_xavier",
        "interval": 2,
        "port": 9100,
        "reload_port": 9101
    },
    "rpi-sensor-01": {
        "device_type": "raspberry_pi",
        "interval": 5,
        "port": 9100,
        "reload_port": 9101
    },
    "shelly-plug-01": {
        "device_type": "shelly",
        "interval": 10,
        "port": 9100,
        "reload_port": 9101,
        "shelly": {
            "host": "192.168.1.100",
            "switch_id": 0
        }
    }
}

@app.route('/config/<device_id>', methods=['GET'])
def get_config(device_id):
    """
    Get configuration for a specific device.

    Args:
        device_id: Device hostname (from URL path)

    Returns:
        JSON configuration object (200) or error (404)
    """
    logger.info(f"Config request for device: {device_id}")

    if device_id in DEVICE_CONFIGS:
        config = DEVICE_CONFIGS[device_id]
        logger.info(f"Returning config for {device_id}: {config['device_type']}")
        return jsonify(config), 200
    else:
        logger.warning(f"Device not found: {device_id}")
        return jsonify({
            "error": "Device not found",
            "device_id": device_id,
            "message": "No configuration available for this device"
        }), 404

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "config-server",
        "version": "1.0.0"
    }), 200

@app.errorhandler(404)
def not_found(error):
    """Custom 404 handler"""
    return jsonify({
        "error": "Not found",
        "message": str(error)
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Custom 500 handler"""
    logger.error(f"Internal error: {error}")
    return jsonify({
        "error": "Internal server error",
        "message": "An unexpected error occurred"
    }), 500

if __name__ == '__main__':
    logger.info("Starting CONFIG SERVER on port 8080")
    app.run(host='0.0.0.0', port=8080, debug=False)
```

**Save as:** `config_server.py`

**Run:**
```bash
python config_server.py
```

### Python FastAPI Server

Modern async implementation:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging

app = FastAPI(title="CONFIG SERVER", version="1.0.0")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for type safety
class DeviceConfig(BaseModel):
    device_type: str = Field(..., description="Device collector type")
    interval: int = Field(1, description="Collection interval in seconds", ge=1)
    port: int = Field(9100, description="Metrics server port", ge=1024, le=65535)
    reload_port: int = Field(9101, description="Reload trigger port", ge=1024, le=65535)
    enabled_metrics: Optional[List[str]] = Field(None, description="Specific metrics to collect")
    jetson: Optional[Dict[str, Any]] = Field(None, description="Jetson-specific config")
    shelly: Optional[Dict[str, Any]] = Field(None, description="Shelly-specific config")
    ina260: Optional[Dict[str, Any]] = Field(None, description="INA260-specific config")

# Device database
DEVICE_CONFIGS: Dict[str, DeviceConfig] = {
    "edge-01": DeviceConfig(
        device_type="jetson_orin",
        interval=1,
        enabled_metrics=["jetson_power_vdd_gpu_soc_watts", "jetson_temp_cpu_celsius"]
    ),
    "edge-02": DeviceConfig(
        device_type="jetson_xavier",
        interval=2
    )
}

@app.get("/config/{device_id}", response_model=DeviceConfig)
async def get_config(device_id: str):
    """Get configuration for a specific device"""
    logger.info(f"Config request for device: {device_id}")

    if device_id not in DEVICE_CONFIGS:
        logger.warning(f"Device not found: {device_id}")
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Device not found",
                "device_id": device_id
            }
        )

    config = DEVICE_CONFIGS[device_id]
    logger.info(f"Returning config for {device_id}: {config.device_type}")
    return config

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "config-server"}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

**Install dependencies:**
```bash
pip install fastapi uvicorn pydantic
```

**Run:**
```bash
uvicorn config_server:app --host 0.0.0.0 --port 8080
```

### Node.js Express Server

```javascript
const express = require('express');
const app = express();
const PORT = 8080;

// Device configuration database
const deviceConfigs = {
  'edge-01': {
    device_type: 'jetson_orin',
    interval: 1,
    port: 9100,
    reload_port: 9101,
    enabled_metrics: [
      'jetson_power_vdd_gpu_soc_watts',
      'jetson_temp_cpu_celsius'
    ]
  },
  'edge-02': {
    device_type: 'jetson_xavier',
    interval: 2,
    port: 9100,
    reload_port: 9101
  }
};

app.get('/config/:deviceId', (req, res) => {
  const deviceId = req.params.deviceId;
  console.log(`Config request for device: ${deviceId}`);

  const config = deviceConfigs[deviceId];

  if (config) {
    console.log(`Returning config for ${deviceId}: ${config.device_type}`);
    res.json(config);
  } else {
    console.warn(`Device not found: ${deviceId}`);
    res.status(404).json({
      error: 'Device not found',
      device_id: deviceId
    });
  }
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`CONFIG SERVER running on port ${PORT}`);
});
```

**Install:**
```bash
npm install express
```

**Run:**
```bash
node config_server.js
```

---

## Testing Guide

### Manual Testing

#### 1. Test Successful Config Fetch

```bash
curl -v http://localhost:8080/config/edge-01
```

**Expected Response:**
```
HTTP/1.1 200 OK
Content-Type: application/json

{
  "device_type": "jetson_orin",
  "interval": 1,
  "port": 9100,
  "reload_port": 9101
}
```

#### 2. Test Device Not Found

```bash
curl -v http://localhost:8080/config/unknown-device
```

**Expected Response:**
```
HTTP/1.1 404 Not Found
Content-Type: application/json

{
  "error": "Device not found",
  "device_id": "unknown-device"
}
```

#### 3. Test Health Check

```bash
curl http://localhost:8080/health
```

**Expected Response:**
```json
{
  "status": "healthy"
}
```

#### 4. Test Response Time

```bash
time curl http://localhost:8080/config/edge-01
```

**Requirement:** Response time must be < 5 seconds (ideally < 100ms).

#### 5. Test JSON Validity

```bash
curl http://localhost:8080/config/edge-01 | jq .
```

**Requirement:** Must be valid JSON parseable by `jq`.

### Integration Testing with Client

#### 1. Setup Test Environment

**Terminal 1 - Start CONFIG SERVER:**
```bash
python config_server.py
```

**Terminal 2 - Configure and start client:**
```bash
export CONFIG_SERVER_URL=http://localhost:8080
export CONFIG_TIMEOUT=5
python exporter.py
```

**Expected Client Output:**
```
INFO:config_loader:Fetching config from http://localhost:8080/config/edge-01
INFO:config_loader:✅ Loaded config from central server
INFO:exporter:Starting edge-metrics-exporter...
INFO:exporter:Device type: jetson_orin
INFO:exporter:Metrics port: 9100
INFO:exporter:Collection interval: 1s
```

#### 2. Test Fallback Mechanism

**Stop CONFIG SERVER** (Ctrl+C in Terminal 1)

**Trigger reload on client:**
```bash
curl -X POST http://localhost:9101/reload
```

**Expected Client Output:**
```
WARNING:config_loader:⚠️ Failed to fetch from central server: ...
INFO:config_loader:✅ Loaded local fallback config
```

#### 3. Test Dynamic Reload

**Start CONFIG SERVER again**

**Update device config in server** (e.g., change `interval` from 1 to 5)

**Trigger reload:**
```bash
curl -X POST http://localhost:9101/reload
```

**Expected Client Output:**
```
INFO:config_loader:Fetching config from http://localhost:8080/config/edge-01
INFO:config_loader:✅ Loaded config from central server
INFO:exporter:🔄 Config reloaded - interval changed to 5s
```

### Automated Testing Script

```bash
#!/bin/bash

SERVER_URL="http://localhost:8080"

echo "Testing CONFIG SERVER at $SERVER_URL"
echo "======================================="

# Test 1: Valid device
echo -e "\n[Test 1] Valid device (edge-01):"
response=$(curl -s -o /dev/null -w "%{http_code}" $SERVER_URL/config/edge-01)
if [ "$response" = "200" ]; then
    echo "✅ PASS - Status code 200"
else
    echo "❌ FAIL - Expected 200, got $response"
fi

# Test 2: Invalid device
echo -e "\n[Test 2] Invalid device (unknown-99):"
response=$(curl -s -o /dev/null -w "%{http_code}" $SERVER_URL/config/unknown-99)
if [ "$response" = "404" ]; then
    echo "✅ PASS - Status code 404"
else
    echo "❌ FAIL - Expected 404, got $response"
fi

# Test 3: JSON validity
echo -e "\n[Test 3] Valid JSON response:"
json=$(curl -s $SERVER_URL/config/edge-01)
if echo "$json" | jq empty 2>/dev/null; then
    echo "✅ PASS - Valid JSON"
else
    echo "❌ FAIL - Invalid JSON"
fi

# Test 4: Required field (device_type)
echo -e "\n[Test 4] Required field 'device_type':"
device_type=$(curl -s $SERVER_URL/config/edge-01 | jq -r '.device_type')
if [ -n "$device_type" ] && [ "$device_type" != "null" ]; then
    echo "✅ PASS - device_type present: $device_type"
else
    echo "❌ FAIL - device_type missing"
fi

# Test 5: Response time
echo -e "\n[Test 5] Response time < 5 seconds:"
start=$(date +%s.%N)
curl -s $SERVER_URL/config/edge-01 > /dev/null
end=$(date +%s.%N)
duration=$(echo "$end - $start" | bc)
if (( $(echo "$duration < 5" | bc -l) )); then
    echo "✅ PASS - Response time: ${duration}s"
else
    echo "❌ FAIL - Response time: ${duration}s (> 5s)"
fi

echo -e "\n======================================="
echo "Testing complete"
```

**Save as:** `test_config_server.sh`

**Run:**
```bash
chmod +x test_config_server.sh
./test_config_server.sh
```

---

## Code References

All file paths are relative to the edge-metrics-exporter repository root.

### Client Implementation Files

| Component | File | Lines | Description |
|-----------|------|-------|-------------|
| **API Client** | [config_loader.py](config_loader.py) | 69-87 | HTTP GET request to CONFIG SERVER |
| **Device ID** | [config_loader.py](config_loader.py) | 36 | `socket.gethostname()` |
| **Timeout Config** | [config_loader.py](config_loader.py) | 35 | `CONFIG_TIMEOUT` env var |
| **Fallback Logic** | [config_loader.py](config_loader.py) | 49-67 | Server → local config fallback |
| **Config Usage** | [exporter.py](exporter.py) | 242-244 | How config is used |
| **Reload Trigger** | [exporter.py](exporter.py) | 44-50, 272-282 | HTTP POST /reload handler |
| **Device Types** | [collectors/__init__.py](collectors/__init__.py) | 24-42 | Valid device_type values |
| **Jetson Metrics** | [collectors/jetson.py](collectors/jetson.py) | 93-226 | Available Jetson metrics |
| **Example Config** | [config.yaml](config.yaml) | - | Local fallback config example |
| **Service Config** | [edge-metrics-exporter.service](edge-metrics-exporter.service) | 13-15 | Environment variables |

### Key Code Snippets

#### Client API Request

**File:** [config_loader.py:79-87](config_loader.py#L79-L87)

```python
url = f"{self.config_server_url}/config/{self.device_id}"
self.logger.info(f"Fetching config from {url}")

response = requests.get(url, timeout=self.timeout)
response.raise_for_status()

config = response.json()
self.logger.info(f"Successfully fetched config from server")
return config
```

#### Fallback Mechanism

**File:** [config_loader.py:49-67](config_loader.py#L49-L67)

```python
def load(self) -> Dict[str, Any]:
    """Load config: try central server, fallback to local"""

    # 1. Try central Config API
    try:
        config = self._fetch_from_server()
        if config:
            self.logger.info("✅ Loaded config from central server")
            return config
    except Exception as e:
        self.logger.warning(f"⚠️ Failed to fetch from central server: {e}")

    # 2. Fallback: local config.yaml
    try:
        config = self._load_local_config()
        self.logger.info("✅ Loaded local fallback config")
        return config
    except Exception as e:
        self.logger.error(f"❌ Failed to load local config: {e}")
        raise RuntimeError(
            "No config available - both central server and local config failed"
        )
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Power Exporter Client                        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Startup / Config Reload Trigger                          │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                          │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  ConfigLoader.load()                                      │  │
│  │  - device_id = socket.gethostname()                      │  │
│  │  - timeout = 5 seconds                                    │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                          │
│                       │ 1. Try Central Server                   │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  HTTP GET Request                                         │  │
│  │  URL: {server}/config/{device_id}                        │  │
│  │  Timeout: 5s                                              │  │
│  │  Example: http://localhost:8080/config/edge-01           │  │
│  └────────┬──────────────────────────┬──────────────────────┘  │
│           │                          │                          │
│    Success│                          │ Fail (timeout/error)    │
│           │                          │                          │
│           ▼                          ▼                          │
│  ┌─────────────────┐    ┌──────────────────────────────────┐  │
│  │ Parse JSON      │    │ 2. Fallback to Local Config      │  │
│  │ Validate        │    │ Load config.yaml from disk        │  │
│  │ device_type     │    │                                   │  │
│  └────────┬────────┘    └────────────┬─────────────────────┘  │
│           │                          │                          │
│           └───────────┬──────────────┘                          │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Apply Configuration                                      │  │
│  │  - Initialize collector (device_type)                    │  │
│  │  - Set collection interval                               │  │
│  │  - Configure ports                                        │  │
│  │  - Filter enabled_metrics                                │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                          │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Start Services                                           │  │
│  │  - Prometheus metrics server (port 9100)                 │  │
│  │  - Config reload server (port 9101)                      │  │
│  │  - Metrics collection loop                               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                       │
                       │ HTTP GET with timeout
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                     CONFIG SERVER                                │
│                     (To be implemented)                          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Endpoint: GET /config/{device_id}                        │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                          │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  1. Extract device_id from URL path                      │  │
│  │     Example: /config/edge-01 → device_id = "edge-01"     │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                          │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  2. Lookup device configuration in database              │  │
│  │     Database: PostgreSQL, MongoDB, or in-memory dict     │  │
│  └────────┬──────────────────────┬──────────────────────────┘  │
│           │                      │                              │
│     Found │                      │ Not Found                   │
│           ▼                      ▼                              │
│  ┌─────────────────┐    ┌───────────────────────────────────┐ │
│  │ 3a. Build JSON  │    │ 3b. Return 404 Error              │ │
│  │ response with:  │    │ {                                 │ │
│  │ - device_type   │    │   "error": "Device not found"     │ │
│  │ - interval      │    │ }                                 │ │
│  │ - port          │    └───────────────────────────────────┘ │
│  │ - reload_port   │                                           │
│  │ - enabled_metrics│                                          │
│  └────────┬────────┘                                           │
│           │                                                     │
│           ▼                                                     │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  4. Return HTTP 200 OK                                    │ │
│  │  Content-Type: application/json                           │ │
│  │  {                                                         │ │
│  │    "device_type": "jetson_orin",                          │ │
│  │    "interval": 1,                                         │ │
│  │    "port": 9100,                                          │ │
│  │    "reload_port": 9101,                                   │ │
│  │    "enabled_metrics": [...]                               │ │
│  │  }                                                         │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Deployment Checklist

### Server Requirements

- [ ] HTTP server listening on port 8080 (configurable)
- [ ] Implements `GET /config/{device_id}` endpoint
- [ ] Returns JSON responses with `Content-Type: application/json`
- [ ] Response time < 5 seconds (ideally < 100ms)
- [ ] Returns 404 for unknown devices
- [ ] Includes required field `device_type` in all successful responses
- [ ] Supports device-specific configuration per device ID
- [ ] Optional: Implements health check endpoint (`/health`)

### Production Recommendations

- [ ] Use HTTPS instead of HTTP
- [ ] Implement authentication (API key, mTLS, etc.)
- [ ] Set up logging for all API requests
- [ ] Configure monitoring and alerting
- [ ] Use a real database (PostgreSQL, MongoDB, etc.) instead of in-memory dict
- [ ] Implement caching for frequently requested configs
- [ ] Set up high availability (load balancer, multiple instances)
- [ ] Configure rate limiting to prevent abuse
- [ ] Document API versioning strategy
- [ ] Create admin API for updating device configurations
- [ ] Implement audit logging for config changes

### Client Configuration

- [ ] Set `CONFIG_SERVER_URL` environment variable to server URL
- [ ] Verify local `config.yaml` exists as fallback
- [ ] Test fallback mechanism (stop server, verify client continues)
- [ ] Test dynamic reload (`POST /reload`)
- [ ] Configure `CONFIG_TIMEOUT` if needed (default 5s)
- [ ] Update systemd service file with environment variables
- [ ] Verify client can reach server (firewall rules, network routing)

---

## FAQ

### Q: What happens if the CONFIG SERVER is down?

**A:** The client automatically falls back to its local `config.yaml` file and continues operating normally. No service interruption occurs.

### Q: Can I update a device's configuration without restarting the client?

**A:** Yes! Trigger a reload by sending `POST http://device:9101/reload`. The client will fetch fresh config from the server and apply it dynamically.

### Q: What if I need to add a new device?

**A:** Simply add the device's configuration to your CONFIG SERVER database with the device's hostname as the key. When the new device starts, it will automatically fetch its config.

### Q: Is authentication required?

**A:** Not in the current implementation. For production deployments, implement network-level security (VPN, firewall) or add authentication to the server.

### Q: How do I know what metrics are available for my device type?

**A:** Check the collector implementation files in the `collectors/` directory. For Jetson devices, see [collectors/jetson.py](collectors/jetson.py).

### Q: Can I use a database instead of hardcoded configs?

**A:** Yes! The implementation examples use in-memory dicts for simplicity. In production, use PostgreSQL, MongoDB, Redis, or any database to store device configurations.

### Q: What's the expected response time?

**A:** The client has a 5-second timeout. Server responses should be much faster (< 100ms) for optimal performance.

### Q: Can I change the port or interval dynamically?

**A:** Yes! Update the configuration in the CONFIG SERVER, then trigger a reload on the client. The new port/interval will be applied without restart.

---

## Summary

This specification provides everything needed to implement a CONFIG SERVER compatible with the edge-metrics-exporter client:

- **Single endpoint:** `GET /config/{device_id}`
- **JSON response** with device-specific configuration
- **Required field:** `device_type`
- **Optional fields:** `interval`, `port`, `reload_port`, `enabled_metrics`
- **Error handling:** 404 for unknown devices, fallback to local config on any error
- **No authentication** (current implementation)
- **Fast response time:** < 5 seconds
- **High availability:** Client continues operation even if server is down

The client is resilient, supports dynamic reload, and provides complete fallback mechanisms for uninterrupted operation.

---

**Document Version:** 1.0
**Last Updated:** 2025-11-18
**Based on Client Version:** edge-metrics-exporter (current codebase)
**Contact:** See repository for issues/questions
