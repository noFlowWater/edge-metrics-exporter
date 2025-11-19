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
from datetime import datetime

from prometheus_client import REGISTRY, start_http_server
from prometheus_client.core import GaugeMetricFamily

from config_loader import ConfigLoader
from collectors import get_collector, BaseCollector


# Global state
current_config = None
current_collector = None
config_loader_instance = None
reload_flag = False

# Health check state
start_time = None
last_collection_time = None
last_collection_error = None

# Thread-safety locks
config_lock = Lock()


class OnDemandCollector:
    """
    Custom Prometheus collector that collects metrics on-demand.
    Only collects when Prometheus scrapes /metrics endpoint.
    """

    def __init__(self):
        self.hostname = socket.gethostname()

    def collect(self):
        """Called by Prometheus when scraping /metrics"""
        global current_config, current_collector, last_collection_time, last_collection_error
        global config_loader_instance

        if not current_collector or not current_config:
            return

        try:
            # Collect metrics from hardware
            metrics = current_collector.safe_get_metrics()

            if not metrics:
                last_collection_error = "No metrics collected"
                return

            # Update health check state
            last_collection_time = datetime.now()
            last_collection_error = None

            # Get config
            with config_lock:
                metrics_config = current_config.get("metrics", {})
                device_type = current_config.get("device_type", "unknown")

                # Auto-discover new metrics
                current_metric_names = set(metrics.keys())
                registered_metric_names = set(metrics_config.keys())
                new_metrics = current_metric_names - registered_metric_names

                if new_metrics:
                    # Add new metrics with enabled=False
                    for metric_name in new_metrics:
                        metrics_config[metric_name] = False
                    current_config["metrics"] = metrics_config

                    # Save to local and sync to server
                    if config_loader_instance:
                        if config_loader_instance.save_to_local(current_config):
                            logger.info(f"Registered {len(new_metrics)} new metrics (disabled): {sorted(new_metrics)}")
                            config_loader_instance.sync_to_server(current_config)

            # Yield metrics for enabled ones only
            for name, value in metrics.items():
                enabled = metrics_config.get(name, False)

                if enabled:
                    gauge = GaugeMetricFamily(
                        name,
                        f"Metric: {name}",
                        labels=["device_type", "hostname"]
                    )
                    gauge.add_metric([device_type, self.hostname], value)
                    yield gauge

        except Exception as e:
            logger.error(f"❌ Metric collection failed: {e}")
            last_collection_error = str(e)

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
        elif self.path == '/health':
            self._handle_health()
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

    def _handle_health(self):
        """Handle GET /health endpoint for device status"""
        global current_config, start_time, last_collection_time, last_collection_error

        try:
            import json

            with config_lock:
                device_id = socket.gethostname()
                device_type = current_config.get("device_type", "unknown")
                metrics_config = current_config.get("metrics", {})

            # Calculate uptime
            uptime_seconds = 0
            if start_time:
                uptime_seconds = int((datetime.now() - start_time).total_seconds())

            # Count metrics
            total_metrics = len(metrics_config)
            enabled_metrics = sum(1 for enabled in metrics_config.values() if enabled)

            # Determine status
            if last_collection_error:
                status = "degraded"
            elif last_collection_time:
                status = "healthy"
            else:
                status = "starting"

            # Build response
            response = {
                "status": status,
                "device_id": device_id,
                "device_type": device_type,
                "uptime_seconds": uptime_seconds,
                "last_collection": last_collection_time.isoformat() if last_collection_time else None,
                "last_error": last_collection_error,
                "metrics_count": total_metrics,
                "enabled_metrics": enabled_metrics
            }

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response, indent=2).encode())

        except Exception as e:
            logger.error(f"Error handling /health: {e}")
            self.send_error(500, f"Internal server error: {e}")

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
    logger.info(f"   - GET  :{port}/health - Health check status")
    logger.info(f"   - POST :{port}/reload - Trigger config reload")
    logger.info(f"   - GET  :{port}/metrics/list - List all metrics")
    logger.info(f"   - POST :{port}/metrics/enable - Enable/disable metrics")


def initialize_collector(config: dict) -> BaseCollector:
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


def apply_new_config(new_config: dict):
    """
    Apply new configuration and reinitialize collector if needed.

    Args:
        new_config: New configuration dictionary
    """
    global current_config, current_collector

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
            logger.info("✅ Collector reinitialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to reinitialize collector: {e}")
            logger.warning("Keeping old collector")
            return

    # Log metrics config changes
    old_metrics = current_config.get("metrics", {})
    new_metrics = new_config.get("metrics", {})

    old_enabled = {k for k, v in old_metrics.items() if v}
    new_enabled = {k for k, v in new_metrics.items() if v}

    added = new_enabled - old_enabled
    removed = old_enabled - new_enabled

    if added:
        logger.info(f"Metrics enabled: {added}")
    if removed:
        logger.info(f"Metrics disabled: {removed}")

    # Apply new config
    with config_lock:
        current_config = new_config
    logger.info("✅ Configuration updated")


def main():
    """Main exporter entry point"""
    global current_config, current_collector, config_loader_instance, reload_flag
    global start_time

    logger.info("🚀 Power Exporter starting...")
    start_time = datetime.now()

    # Load initial configuration
    config_loader_instance = ConfigLoader()
    current_config = config_loader_instance.load()
    logger.info(f"Configuration: {current_config}")

    # Initialize collector
    current_collector = initialize_collector(current_config)

    # Register custom collector for on-demand metrics
    REGISTRY.register(OnDemandCollector())
    logger.info("✅ On-demand collector registered")

    # Start Prometheus HTTP server
    metrics_port = current_config.get("port", 9100)
    start_http_server(metrics_port)
    logger.info(f"📊 Prometheus metrics endpoint started on :{metrics_port}/metrics")

    # Start management API server
    reload_port = current_config.get("reload_port", 9101)
    start_reload_server(reload_port)

    logger.info("✅ Exporter fully initialized - waiting for scrape requests")

    # Keep main thread alive and handle reload requests
    while True:
        if reload_flag:
            try:
                logger.info("🔄 Reloading configuration...")
                new_config = config_loader_instance.load()
                apply_new_config(new_config)
                reload_flag = False
            except Exception as e:
                logger.error(f"❌ Config reload failed: {e}")
                reload_flag = False

        time.sleep(1)  # Check reload flag every second


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Exporter stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        exit(1)
