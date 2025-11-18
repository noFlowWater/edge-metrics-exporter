#!/usr/bin/env python3
"""
Power Exporter - Prometheus exporter for edge device power consumption.

Supports:
- Multiple device types with pluggable collectors
- Central config server with local fallback
- Dynamic config reload via HTTP endpoint
- Prometheus metrics exposition
"""
import logging
import socket
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Lock
from typing import Dict

from prometheus_client import Gauge, start_http_server

from config_loader import ConfigLoader
from collectors import get_collector, BaseCollector


# Global state
current_config = None
current_collector = None
gauges = {}
reload_flag = False

# Thread-safety locks
config_lock = Lock()
gauges_lock = Lock()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ReloadHandler(BaseHTTPRequestHandler):
    """
    HTTP handler for config reload trigger endpoint.
    POST /reload triggers a config reload.
    """

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
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not Found\n')

    def log_message(self, format, *args):
        """Suppress default HTTP request logs"""
        pass


class MetricsConfigHandler(BaseHTTPRequestHandler):
    """
    HTTP handler for metrics configuration API.
    GET /metrics/list - List all metrics and their enabled status
    POST /metrics/enable - Enable/disable specific metrics
    """

    def do_GET(self):
        """Handle GET requests"""
        global current_config

        if self.path == '/metrics/list':
            try:
                with config_lock:
                    metrics_config = current_config.get("metrics", {})
                    response = {
                        "metrics": metrics_config,
                        "device_type": current_config.get("device_type"),
                        "source": "local"
                    }

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()

                import json
                self.wfile.write(json.dumps(response, indent=2).encode())

            except Exception as e:
                logger.error(f"Error handling /metrics/list: {e}")
                self.send_error(500, f"Internal server error: {e}")

        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not Found\n')

    def do_POST(self):
        """Handle POST requests"""
        global current_config

        if self.path == '/metrics/enable':
            try:
                # Read and parse request body
                content_length = int(self.headers.get('Content-Length', 0))

                # Size limit check (100KB)
                if content_length > 1024 * 100:
                    self.send_error(413, "Request too large")
                    return

                body = self.rfile.read(content_length)

                import json
                updates = json.loads(body.decode())

                # Validate input
                if not isinstance(updates, dict):
                    self.send_error(400, "Request body must be a JSON object")
                    return

                # Count limit check
                if len(updates) > 1000:
                    self.send_error(400, "Too many metrics (max 1000)")
                    return

                # Update metrics configuration
                with config_lock:
                    metrics_config = current_config.get("metrics", {})

                    invalid_metrics = []
                    updated_count = 0

                    for metric_name, enabled in updates.items():
                        # Type validation
                        if not isinstance(enabled, bool):
                            self.send_error(400, f"Invalid type for {metric_name}: expected bool")
                            return

                        # Check if metric exists in config
                        if metric_name not in metrics_config:
                            invalid_metrics.append(metric_name)
                        else:
                            metrics_config[metric_name] = enabled
                            updated_count += 1

                    if invalid_metrics:
                        self.send_error(400, f"Unknown metrics: {invalid_metrics}")
                        return

                    current_config["metrics"] = metrics_config

                    # Save to local config file
                    loader = ConfigLoader()
                    if loader.save_to_local(current_config):
                        logger.info(f"Updated {updated_count} metrics via API: {updates}")

                        # Sync to server (non-blocking, background)
                        loader.sync_to_server(current_config)

                        response = {
                            "status": "success",
                            "updated": updated_count,
                            "metrics": updates
                        }

                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(response, indent=2).encode())
                    else:
                        self.send_error(500, "Failed to save configuration")

            except json.JSONDecodeError as e:
                self.send_error(400, f"Invalid JSON: {e}")
            except Exception as e:
                logger.error(f"Error handling /metrics/enable: {e}")
                self.send_error(500, f"Internal server error: {e}")

        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not Found\n')

    def log_message(self, format, *args):
        """Suppress default HTTP request logs"""
        pass


class CombinedHandler(BaseHTTPRequestHandler):
    """Combined handler for both reload and metrics config endpoints"""

    def do_GET(self):
        if self.path == '/metrics/list':
            MetricsConfigHandler.do_GET(self)
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not Found\n')

    def do_POST(self):
        if self.path == '/reload':
            ReloadHandler.do_POST(self)
        elif self.path == '/metrics/enable':
            MetricsConfigHandler.do_POST(self)
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not Found\n')

    def log_message(self, format, *args):
        """Suppress default HTTP request logs"""
        pass


def start_reload_server(port: int):
    """
    Start HTTP server for reload and metrics config endpoints in a separate thread.

    Args:
        port: Port to listen on (e.g., 9101)
    """
    server = HTTPServer(('0.0.0.0', port), CombinedHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"🔄 Management API started on :{port}")
    logger.info(f"   - POST :{port}/reload - Trigger config reload")
    logger.info(f"   - GET  :{port}/metrics/list - List all metrics")
    logger.info(f"   - POST :{port}/metrics/enable - Enable/disable metrics")


def initialize_collector(config: Dict) -> BaseCollector:
    """
    Initialize collector based on config.

    Args:
        config: Configuration dictionary

    Returns:
        Initialized collector instance
    """
    device_type = config["device_type"]
    logger.info(f"Initializing collector for device type: {device_type}")

    try:
        collector = get_collector(device_type, config)
        logger.info(f"✅ Collector initialized: {collector.__class__.__name__}")
        return collector
    except Exception as e:
        logger.error(f"❌ Failed to initialize collector: {e}")
        raise


def initialize_gauges(collector: BaseCollector, config: Dict) -> Dict[str, Gauge]:
    """
    Initialize Prometheus gauges for enabled metrics.

    Args:
        collector: Collector instance
        config: Configuration dictionary

    Returns:
        Dictionary mapping metric names to Gauge objects
    """
    gauges = {}
    metrics_config = config.get("metrics", {})

    # If metrics config is empty, don't initialize any gauges
    # They will be created dynamically when metrics are enabled
    if not metrics_config:
        logger.info("No metrics configured, gauges will be created dynamically")
        return gauges

    # Initialize gauges only for enabled metrics
    for metric_name, enabled in metrics_config.items():
        if enabled:
            gauges[metric_name] = Gauge(
                metric_name,
                f"Metric: {metric_name}",
                ["device_type", "hostname"]
            )

    logger.info(f"✅ Initialized {len(gauges)} Prometheus gauges for enabled metrics")
    return gauges


def apply_new_config(new_config: Dict):
    """
    Apply new configuration and reinitialize collector if needed.

    Args:
        new_config: New configuration dictionary
    """
    global current_config, current_collector, gauges

    old_device_type = current_config.get("device_type")
    new_device_type = new_config.get("device_type")

    # If device type changed, reinitialize collector
    if old_device_type != new_device_type:
        logger.info(
            f"Device type changed: {old_device_type} → {new_device_type}"
        )
        logger.info("Reinitializing collector...")

        try:
            current_collector = initialize_collector(new_config)
            gauges = initialize_gauges(current_collector, new_config)
            logger.info("✅ Collector reinitialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to reinitialize collector: {e}")
            logger.warning("Keeping old collector")
            return

    # Log other config changes
    old_interval = current_config.get("interval", 1)
    new_interval = new_config.get("interval", 1)
    if old_interval != new_interval:
        logger.info(f"Interval changed: {old_interval}s → {new_interval}s")

    old_enabled = set(
        current_config.get("enabled_metrics", current_collector.metric_names())
    )
    new_enabled = set(
        new_config.get("enabled_metrics", current_collector.metric_names())
    )

    added = new_enabled - old_enabled
    removed = old_enabled - new_enabled

    if added:
        logger.info(f"Metrics enabled: {added}")
    if removed:
        logger.info(f"Metrics disabled: {removed}")

    # Apply new config
    current_config = new_config
    logger.info("✅ Configuration updated")


def collect_and_update_metrics(
    collector: BaseCollector,
    gauges: Dict[str, Gauge],
    config: Dict,
    hostname: str,
    device_type: str
):
    """
    Collect metrics from collector and update Prometheus gauges.

    Args:
        collector: Collector instance
        gauges: Dictionary of Prometheus gauges
        config: Configuration dictionary
        hostname: Hostname for label
        device_type: Device type for label
    """
    try:
        # Collect metrics
        metrics = collector.safe_get_metrics()

        if not metrics:
            logger.warning("No metrics collected")
            return

        # Get metrics configuration (new dict format)
        with config_lock:
            metrics_config = config.get("metrics", {})

            # Backward compatibility: convert enabled_metrics list to metrics dict
            if "enabled_metrics" in config and not metrics_config:
                logger.info("Converting enabled_metrics list to metrics dict format")
                for metric_name in config["enabled_metrics"]:
                    metrics_config[metric_name] = True
                config["metrics"] = metrics_config
                # Remove old format
                del config["enabled_metrics"]

            # If metrics config is empty, default to all metrics disabled
            if not metrics_config:
                metrics_config = {}

        # Update gauges - create new gauges dynamically if needed
        for name, value in metrics.items():
            # Check if metric is enabled (default to False)
            enabled = metrics_config.get(name, False)

            if enabled:
                with gauges_lock:
                    # Create gauge if it doesn't exist (for dynamically discovered metrics)
                    if name not in gauges:
                        logger.info(f"Creating new gauge for discovered metric: {name}")
                        gauges[name] = Gauge(
                            name,
                            f"Metric: {name}",
                            ["device_type", "hostname"]
                        )

                # Update the gauge (outside lock to minimize contention)
                gauges[name].labels(
                    device_type=device_type,
                    hostname=hostname
                ).set(value)

        logger.debug(f"Updated {len([m for m in metrics if metrics_config.get(m, False)])} metrics")

    except Exception as e:
        logger.error(f"❌ Metric collection failed: {e}")


def update_metrics_registry(
    metrics_dict: Dict[str, float],
    config: Dict,
    config_loader: ConfigLoader
) -> bool:
    """
    Update metrics registry with newly discovered metrics.
    New metrics are added with enabled=False by default.

    Args:
        metrics_dict: Dictionary of collected metrics
        config: Current configuration dictionary
        config_loader: ConfigLoader instance for saving

    Returns:
        True if config was updated and saved, False otherwise
    """
    # Safety check: don't process empty metrics
    if not metrics_dict:
        logger.debug("Empty metrics dict, skipping registry update")
        return False

    with config_lock:
        metrics_config = config.get("metrics", {})

        # Find new metrics that aren't in config yet
        current_metric_names = set(metrics_dict.keys())
        registered_metric_names = set(metrics_config.keys())
        new_metrics = current_metric_names - registered_metric_names

        if new_metrics:
            # Add new metrics with enabled=False
            for metric_name in new_metrics:
                metrics_config[metric_name] = False

            config["metrics"] = metrics_config

            # Save to local config file
            if config_loader.save_to_local(config):
                logger.info(f"Registered {len(new_metrics)} new metrics (disabled): {sorted(new_metrics)}")

                # Sync to server (non-blocking, background)
                config_loader.sync_to_server(config)

                return True
            else:
                logger.error("Failed to save config after discovering new metrics")
                return False

    return False


def main():
    """Main exporter loop"""
    global current_config, current_collector, gauges, reload_flag

    logger.info("🚀 Power Exporter starting...")

    # Load initial configuration
    loader = ConfigLoader()
    current_config = loader.load()
    logger.info(f"Configuration: {current_config}")

    # Initialize collector
    current_collector = initialize_collector(current_config)

    # Initialize Prometheus gauges
    gauges = initialize_gauges(current_collector, current_config)

    # Start Prometheus HTTP server
    metrics_port = current_config.get("port", 9100)
    start_http_server(metrics_port)
    logger.info(f"📊 Prometheus metrics endpoint started on :{metrics_port}/metrics")

    # Start reload HTTP server
    reload_port = current_config.get("reload_port", 9101)
    start_reload_server(reload_port)

    # Get labels
    hostname = socket.gethostname()
    device_type = current_config["device_type"]

    logger.info("✅ Exporter fully initialized - starting metric collection loop")

    # Main loop
    interval = current_config.get("interval", 1)

    while True:
        # Check for reload flag
        if reload_flag:
            try:
                logger.info("🔄 Reloading configuration...")
                new_config = loader.load()
                apply_new_config(new_config)
                interval = current_config.get("interval", 1)
                device_type = current_config["device_type"]
                reload_flag = False
            except Exception as e:
                logger.error(f"❌ Config reload failed: {e}")
                reload_flag = False

        # Collect metrics first
        metrics = current_collector.safe_get_metrics()

        # Update metrics registry (discover new metrics)
        if metrics:
            update_metrics_registry(metrics, current_config, loader)

        # Update Prometheus gauges
        if metrics:
            collect_and_update_metrics(
                current_collector,
                gauges,
                current_config,
                hostname,
                device_type
            )

        time.sleep(interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Exporter stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        exit(1)
