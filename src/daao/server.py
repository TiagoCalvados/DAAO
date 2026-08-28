from __future__ import annotations

from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import threading

from daao.models import SensorUpdate
from daao.parsing import PayloadError, parse_http_payload


MAX_REQUEST_BYTES = 32 * 1024 * 1024
logger = logging.getLogger(__name__)


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class SensorServer:
    """Small background HTTP receiver for Sensor Logger pushes."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        on_update: Callable[[SensorUpdate], None] | None = None,
        max_request_bytes: int = MAX_REQUEST_BYTES,
    ) -> None:
        self.host = host
        self.requested_port = port
        self.on_update = on_update or (lambda _update: None)
        self.max_request_bytes = max_request_bytes
        self._httpd: ReusableThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        if self._httpd is None:
            return self.requested_port
        return int(self._httpd.server_address[1])

    def start(self) -> None:
        if self._httpd is not None:
            return
        handler = self._make_handler()
        self._httpd = ReusableThreadingHTTPServer((self.host, self.requested_port), handler)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="sensor-logger-http",
            daemon=True,
        )
        self._thread.start()
        logger.info("HTTP receiver listening on %s:%d", self.host, self.port)

    def stop(self) -> None:
        httpd = self._httpd
        thread = self._thread
        self._httpd = None
        self._thread = None
        if httpd is None:
            return
        httpd.shutdown()
        httpd.server_close()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        logger.info("HTTP receiver stopped")

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        receiver = self

        class SensorRequestHandler(BaseHTTPRequestHandler):
            server_version = "DAAO/0.3.3"

            def do_GET(self) -> None:
                logger.info(
                    "HTTP GET client=%s path=%s",
                    self.client_address[0],
                    self.path,
                )
                if self.path not in ("/", "/health"):
                    self._respond(404, {"status": "not found"})
                    return
                self._respond(
                    200,
                    {
                        "status": "ok",
                        "service": "DIY Astronomical Attic Observatory",
                        "endpoint": "/data",
                    },
                )

            def do_POST(self) -> None:
                client = self.client_address[0]
                raw_length = self.headers.get("Content-Length")
                content_type = self.headers.get("Content-Type", "application/json")
                logger.info(
                    "HTTP POST client=%s path=%s content_type=%s content_length=%s",
                    client,
                    self.path,
                    content_type,
                    raw_length,
                )
                if raw_length is None:
                    logger.warning("Rejected POST client=%s: Content-Length required", client)
                    self._respond(411, {"status": "error", "message": "Content-Length required"})
                    return
                try:
                    length = int(raw_length)
                except ValueError:
                    logger.warning("Rejected POST client=%s: invalid Content-Length", client)
                    self._respond(400, {"status": "error", "message": "invalid Content-Length"})
                    return
                if length < 0 or length > receiver.max_request_bytes:
                    logger.warning(
                        "Rejected POST client=%s: request size %d outside allowed range",
                        client,
                        length,
                    )
                    self._respond(413, {"status": "error", "message": "request too large"})
                    return

                body = self.rfile.read(length)
                if self.path.rstrip("/") != "/data":
                    logger.warning("Rejected POST client=%s: unknown path %s", client, self.path)
                    self._respond(404, {"status": "not found"})
                    return
                try:
                    update = parse_http_payload(
                        content_type,
                        body,
                    )
                    receiver.on_update(update)
                except PayloadError as error:
                    logger.warning("Rejected POST client=%s: %s", client, error)
                    self._respond(400, {"status": "error", "message": str(error)})
                    return
                except Exception:
                    logger.exception("Receiver error while processing POST client=%s", client)
                    self._respond(500, {"status": "error", "message": "receiver error"})
                    return
                logger.info(
                    "Accepted sensor update client=%s readings=%d heading=%s "
                    "true_heading=%s heading_accuracy=%s elevation=%s roll=%s image_bytes=%d "
                    "horizontal_fov=%s latitude=%s longitude=%s "
                    "message_id=%s session_id=%s",
                    client,
                    update.reading_count,
                    update.heading,
                    update.true_heading,
                    update.heading_accuracy,
                    update.camera_elevation,
                    update.camera_roll,
                    len(update.image) if update.image is not None else 0,
                    update.horizontal_fov,
                    update.latitude,
                    update.longitude,
                    update.message_id,
                    update.session_id,
                )
                self._respond(200, {"status": "success"})

            def _respond(self, status: int, payload: dict[str, object]) -> None:
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        return SensorRequestHandler

    def __enter__(self) -> SensorServer:
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.stop()
