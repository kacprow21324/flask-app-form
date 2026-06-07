import json
import logging
import time
import uuid
from datetime import datetime, timezone

from flask import Blueprint, Response, current_app, g, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest


metrics_bp = Blueprint("metrics", __name__)
HTTP_REQUESTS = Counter(
    "flask_http_requests_total",
    "Liczba żądań HTTP.",
    ["method", "endpoint", "status"],
)
HTTP_LATENCY = Histogram(
    "flask_http_request_duration_seconds",
    "Czas obsługi żądania HTTP.",
    ["method", "endpoint"],
)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "request_id",
            "method",
            "path",
            "status",
            "duration_ms",
            "remote_addr",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def init_observability(app):
    if app.config.get("JSON_LOGS"):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        app.logger.handlers.clear()
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)

    @app.before_request
    def start_request_metrics():
        g.request_started_at = time.perf_counter()
        supplied = request.headers.get("X-Request-ID", "")
        g.request_id = supplied[:100] if supplied else str(uuid.uuid4())

    @app.after_request
    def finish_request_metrics(response):
        endpoint = request.endpoint or "unknown"
        duration = time.perf_counter() - g.get(
            "request_started_at", time.perf_counter(),
        )
        HTTP_REQUESTS.labels(
            request.method, endpoint, str(response.status_code),
        ).inc()
        HTTP_LATENCY.labels(request.method, endpoint).observe(duration)
        response.headers.setdefault("X-Request-ID", g.get("request_id", ""))
        current_app.logger.info(
            "http_request",
            extra={
                "request_id": g.get("request_id"),
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": round(duration * 1000, 2),
                "remote_addr": request.remote_addr,
            },
        )
        return response


@metrics_bp.get("/metrics")
def metrics():
    return Response(generate_latest(), content_type=CONTENT_TYPE_LATEST)
