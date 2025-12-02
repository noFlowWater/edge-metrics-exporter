#!/usr/bin/env python3
"""
Shelly WebSocket Server
각 디바이스의 쉘리플러그가 연결하여 실시간 전력 데이터를 전송하는 독립 서버
"""
import asyncio
import json
import logging
import os
import time
from threading import Lock
from aiohttp import web
import websockets


class ShellyMetricsCache:
    """
    메트릭 캐시 (Thread-safe)
    각 디바이스의 최신 메트릭을 메모리에 저장
    """

    def __init__(self):
        self.devices = {}  # {device_id: {"metrics": {...}, "timestamp": float}}
        self.lock = Lock()
        self.logger = logging.getLogger("ShellyMetricsCache")

    def update(self, device_id: str, metrics: dict):
        """메트릭 업데이트 (thread-safe)"""
        with self.lock:
            self.devices[device_id] = {
                "metrics": metrics,
                "timestamp": time.time()
            }
            self.logger.debug(f"Updated metrics for {device_id}: {metrics}")

    def get(self, device_id: str) -> dict:
        """메트릭 조회 (thread-safe)"""
        with self.lock:
            device_data = self.devices.get(device_id)

            if not device_data:
                return {}

            # Check if metrics are stale (older than 60 seconds)
            age = time.time() - device_data["timestamp"]
            if age > 60:
                self.logger.warning(f"Metrics for {device_id} are stale ({age:.1f}s old)")

            return device_data.get("metrics", {})

    def get_all_devices(self) -> list:
        """디바이스 목록 조회 (thread-safe)"""
        with self.lock:
            return list(self.devices.keys())

    def remove(self, device_id: str):
        """디바이스 제거 (thread-safe)"""
        with self.lock:
            if device_id in self.devices:
                del self.devices[device_id]
                self.logger.info(f"Removed device: {device_id}")


class ShellyWebSocketHandler:
    """
    WebSocket 연결 처리
    Shelly 플러그의 Outbound WebSocket 연결을 처리하고 RPC 메시지 파싱
    """

    def __init__(self, cache: ShellyMetricsCache):
        self.cache = cache
        self.logger = logging.getLogger("ShellyWebSocketHandler")

    async def handle_connection(self, websocket, path):
        """
        WebSocket 연결 처리 메인 루프

        Args:
            websocket: WebSocket 연결 객체
            path: 연결 경로 (사용 안 함)
        """
        device_id = None
        remote_addr = websocket.remote_address

        try:
            self.logger.info(f"New WebSocket connection from {remote_addr}")

            # 메시지 수신 루프
            async for message in websocket:
                try:
                    # JSON-RPC 메시지 파싱
                    data = self._parse_rpc_message(message)

                    if not data:
                        continue

                    # 디바이스 ID 추출 (첫 메시지에서)
                    if not device_id:
                        device_id = self._extract_device_id(data, remote_addr)
                        if device_id:
                            self.logger.info(f"Device identified: {device_id}")

                    # 메트릭 추출 및 저장
                    metrics = self._extract_metrics(data)
                    if metrics and device_id:
                        self.cache.update(device_id, metrics)

                except Exception as e:
                    self.logger.error(f"Error processing message: {e}")
                    continue

        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"Connection closed: {remote_addr}")
        except Exception as e:
            self.logger.error(f"WebSocket error: {e}")
        finally:
            # 연결 종료 시 디바이스 제거
            if device_id:
                self.cache.remove(device_id)

    def _parse_rpc_message(self, message: str) -> dict:
        """
        JSON-RPC 메시지 파싱

        Args:
            message: 원시 JSON 문자열

        Returns:
            파싱된 딕셔너리 또는 None
        """
        try:
            return json.loads(message)
        except Exception as e:
            self.logger.error(f"Failed to parse RPC message: {e}")
            return None

    def _extract_device_id(self, data: dict, remote_addr: tuple) -> str:
        """
        RPC 메시지에서 디바이스 ID 추출

        Args:
            data: 파싱된 RPC 메시지
            remote_addr: 원격 주소 (IP, port)

        Returns:
            디바이스 ID 문자열
        """
        # Try to get device ID from message "src" field
        if "src" in data:
            return data["src"]

        # Fallback: use remote IP address
        return f"shelly_{remote_addr[0].replace('.', '_')}"

    def _extract_metrics(self, data: dict) -> dict:
        """
        RPC 메시지에서 전력 메트릭 추출
        NotifyFullStatus, NotifyStatus, NotifyEvent 메시지 처리

        Args:
            data: 파싱된 RPC 메시지

        Returns:
            메트릭 딕셔너리 {power_total_watts, power_voltage_volts, power_current_amps}
        """
        metrics = {}

        try:
            method = data.get("method", "")
            params = data.get("params", {})

            # Look for switch:0 data (Shelly plugs use switch:0)
            switch_data = None

            if "switch:0" in params:
                switch_data = params["switch:0"]
            elif isinstance(params, dict):
                # Sometimes params directly contain the metrics
                switch_data = params

            if switch_data and isinstance(switch_data, dict):
                # Extract power metrics
                if "apower" in switch_data:
                    metrics["power_total_watts"] = float(switch_data["apower"])

                if "voltage" in switch_data:
                    metrics["power_voltage_volts"] = float(switch_data["voltage"])

                if "current" in switch_data:
                    metrics["power_current_amps"] = float(switch_data["current"])

        except Exception as e:
            self.logger.error(f"Error extracting metrics: {e}")

        return metrics


class ShellyHTTPHandler:
    """
    HTTP API 처리
    ShellyCollector가 메트릭을 조회할 수 있는 HTTP API 제공
    """

    def __init__(self, cache: ShellyMetricsCache):
        self.cache = cache
        self.logger = logging.getLogger("ShellyHTTPHandler")

    async def handle_metrics(self, request):
        """
        GET /metrics
        현재 연결된 유일한 디바이스의 메트릭 반환 (1:1:1 관계)

        동작:
        - Shelly plug 연결 전: 404 (No Shelly device connected)
        - Shelly plug 연결 후: 메트릭 반환

        Returns:
            JSON 응답
        """
        devices = self.cache.get_all_devices()

        if not devices:
            return web.json_response(
                {"error": "No Shelly device connected"},
                status=404
            )

        # 첫 번째 (유일한) 디바이스의 메트릭 반환
        device_id = devices[0]
        metrics = self.cache.get(device_id)

        if not metrics:
            return web.json_response(
                {"error": "No metrics available"},
                status=404
            )

        return web.json_response({
            "device_id": device_id,
            "metrics": metrics
        })

    async def handle_devices(self, request):
        """
        GET /devices
        연결된 디바이스 목록 반환

        Returns:
            JSON 응답
        """
        devices = self.cache.get_all_devices()

        return web.json_response({
            "devices": devices,
            "count": len(devices)
        })


class ShellyServer:
    """
    메인 서버
    WebSocket 서버와 HTTP API 서버를 동시에 실행
    """

    def __init__(self, ws_port=8765, http_port=8766):
        self.ws_port = ws_port
        self.http_port = http_port

        # 공유 메트릭 캐시
        self.cache = ShellyMetricsCache()

        # 핸들러 초기화
        self.ws_handler = ShellyWebSocketHandler(self.cache)
        self.http_handler = ShellyHTTPHandler(self.cache)

        self.logger = logging.getLogger("ShellyServer")

    async def start_websocket_server(self):
        """WebSocket 서버 시작"""
        try:
            async with websockets.serve(
                self.ws_handler.handle_connection,
                "0.0.0.0",
                self.ws_port,
                ping_interval=30,  # Send ping every 30s
                ping_timeout=10    # Close if no pong after 10s
            ):
                self.logger.info(f"🔌 WebSocket server started on port {self.ws_port}")
                await asyncio.Future()  # Run forever
        except Exception as e:
            self.logger.error(f"❌ WebSocket server failed: {e}")

    async def start_http_server(self):
        """HTTP API 서버 시작"""
        try:
            app = web.Application()

            # 라우트 등록
            app.router.add_get("/metrics", self.http_handler.handle_metrics)
            app.router.add_get("/devices", self.http_handler.handle_devices)

            runner = web.AppRunner(app)
            await runner.setup()

            site = web.TCPSite(runner, "0.0.0.0", self.http_port)
            await site.start()

            self.logger.info(f"🌐 HTTP API server started on port {self.http_port}")
            self.logger.info(f"   - GET :{self.http_port}/metrics")
            self.logger.info(f"   - GET :{self.http_port}/devices")

            await asyncio.Future()  # Run forever
        except Exception as e:
            self.logger.error(f"❌ HTTP server failed: {e}")

    def run(self):
        """서버 시작 (WebSocket + HTTP 동시 실행)"""
        asyncio.run(self._run_both())

    async def _run_both(self):
        """WebSocket과 HTTP 서버를 asyncio.gather로 동시 실행"""
        self.logger.info("🚀 Shelly Server starting...")

        await asyncio.gather(
            self.start_websocket_server(),
            self.start_http_server()
        )


def main():
    """메인 엔트리 포인트"""
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger(__name__)

    # 환경변수에서 포트 읽기
    ws_port = int(os.getenv("SHELLY_WS_PORT", "8765"))
    http_port = int(os.getenv("SHELLY_HTTP_PORT", "8766"))

    logger.info(f"Configuration:")
    logger.info(f"  WebSocket Port: {ws_port}")
    logger.info(f"  HTTP API Port: {http_port}")

    # 서버 시작
    server = ShellyServer(ws_port=ws_port, http_port=http_port)

    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        exit(1)


if __name__ == "__main__":
    main()
