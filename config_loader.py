"""
Configuration loader with central API support and local fallback.
"""
import requests
import yaml
import socket
import logging
import os
from typing import Dict
from threading import Thread


class ConfigLoader:
    """
    Load configuration from central Config API server with local fallback.

    Priority:
    1. Try to fetch from central Config API server (with timeout)
    2. If fails, load from local config.yaml

    Environment variables:
    - CONFIG_SERVER_URL: Central config server URL (default: http://localhost:8080)
    - CONFIG_TIMEOUT: Request timeout in seconds (default: 5)
    - LOCAL_CONFIG_PATH: Path to local config file (default: ./config.yaml)
    """

    def __init__(self):
        self.config_server_url = os.getenv(
            "CONFIG_SERVER_URL",
            "http://localhost:8080"
        )
        self.local_config_path = os.getenv(
            "LOCAL_CONFIG_PATH",
            "./config.yaml"
        )
        self.timeout = int(os.getenv("CONFIG_TIMEOUT", "5"))
        self.device_id = socket.gethostname()
        self.logger = logging.getLogger(self.__class__.__name__)

    def load(self) -> Dict:
        """
        Load configuration with central API + local fallback.

        Returns:
            Configuration dictionary

        Raises:
            RuntimeError: If both central and local config loading fail
        """
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

            # 3. Register device to server (non-blocking)
            self.logger.info("📤 Registering device to server...")
            self.sync_to_server(config)

            return config
        except Exception as e:
            self.logger.error(f"❌ Failed to load local config: {e}")
            raise RuntimeError(
                "No config available - both central server and local config failed"
            )

    def _fetch_from_server(self) -> Dict:
        """
        Fetch configuration from central Config API server.

        Returns:
            Configuration dictionary from server

        Raises:
            Exception: If request fails or server returns error
        """
        url = f"{self.config_server_url}/config/{self.device_id}"
        self.logger.info(f"Fetching config from {url}")

        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()

        config = response.json()
        self.logger.debug(f"Received config: {config}")
        return config

    def _load_local_config(self) -> Dict:
        """
        Load configuration from local config.yaml file.

        Returns:
            Configuration dictionary from local file

        Raises:
            Exception: If file doesn't exist or parsing fails
        """
        self.logger.info(f"Loading config from {self.local_config_path}")

        with open(self.local_config_path, 'r') as f:
            config = yaml.safe_load(f)

        if not config:
            raise ValueError("Local config file is empty")

        self.logger.debug(f"Loaded local config: {config}")
        return config

    def save_to_local(self, config: Dict) -> bool:
        """
        Save configuration to local config.yaml file using atomic write.

        Args:
            config: Configuration dictionary to save

        Returns:
            True if save succeeded, False otherwise
        """
        tmp_path = self.local_config_path + ".tmp"

        try:
            # Write to temporary file first
            with open(tmp_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)

            # Atomic rename (crash-safe)
            os.replace(tmp_path, self.local_config_path)

            self.logger.info(f"Saved config to {self.local_config_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save config to {self.local_config_path}: {e}")

            # Clean up temporary file if it exists
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

            return False

    def sync_to_server(self, config: Dict) -> None:
        """
        Asynchronously sync configuration to Config Server (non-blocking).
        Runs in a background thread to avoid blocking the main loop.

        Args:
            config: Configuration dictionary to sync

        Note:
            This method returns immediately. Sync happens in background.
            Failures are logged but do not affect service operation.
        """
        thread = Thread(
            target=self._sync_worker,
            args=(config, self.device_id),
            daemon=True,
            name="ConfigSyncThread"
        )
        thread.start()
        self.logger.debug(f"Started background sync to server for {self.device_id}")

    def _sync_worker(self, config: Dict, device_id: str) -> None:
        """
        Worker thread for syncing config to server.

        Args:
            config: Configuration dictionary to sync
            device_id: Device identifier
        """
        try:
            url = f"{self.config_server_url}/config/{device_id}"
            self.logger.debug(f"Syncing config to {url}")

            response = requests.put(
                url,
                json=config,
                timeout=self.timeout
            )

            if response.ok:
                self.logger.info(f"Successfully synced config to server")
            else:
                self.logger.warning(
                    f"Server sync failed: HTTP {response.status_code} - {response.text}"
                )

        except requests.exceptions.Timeout:
            self.logger.warning(f"Server sync timeout (>{self.timeout}s)")
        except requests.exceptions.ConnectionError as e:
            self.logger.warning(f"Server sync connection error: {e}")
        except Exception as e:
            self.logger.error(f"Server sync error: {e}")
