import time
from http import HTTPStatus

import requests
from django.conf import settings


class UpstreamError(Exception):
    """An external API (routing, weather, geocoding) failed or returned no usable data."""

    def __init__(self, message: str, status: int = HTTPStatus.BAD_GATEWAY):
        super().__init__(message)
        self.status = status


_session = requests.Session()
_session.headers["User-Agent"] = settings.HTTP_USER_AGENT


RETRY_DELAY_SECONDS = 0.6


def _get(url: str, params: dict | None, service: str) -> requests.Response:
    """GET with one retry for transient failures (network errors, 5xx) of the public servers."""
    try:
        response = _session.get(url, params=params, timeout=settings.HTTP_TIMEOUT_SECONDS)
        if response.status_code < HTTPStatus.INTERNAL_SERVER_ERROR:
            return response
    except requests.RequestException:
        pass
    time.sleep(RETRY_DELAY_SECONDS)
    try:
        return _session.get(url, params=params, timeout=settings.HTTP_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise UpstreamError(f"{service} is unreachable: {exc.__class__.__name__}") from exc


def get_json(url: str, params: dict | None = None, service: str = "upstream"):
    """GET `url` and return its JSON, or raise UpstreamError with a user-facing message."""
    response = _get(url, params, service)
    if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
        raise UpstreamError(
            f"{service} rate limit reached; try again in a minute",
            status=HTTPStatus.SERVICE_UNAVAILABLE,
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise UpstreamError(f"{service} returned HTTP {response.status_code}") from exc
    if response.status_code >= HTTPStatus.BAD_REQUEST:
        reason = data.get("reason") or data.get("message") if isinstance(data, dict) else None
        # A 4xx from upstream usually means the input can't be used (e.g. no route).
        client_error = response.status_code < HTTPStatus.INTERNAL_SERVER_ERROR
        status = HTTPStatus.UNPROCESSABLE_ENTITY if client_error else HTTPStatus.BAD_GATEWAY
        raise UpstreamError(
            f"{service} error: {reason or f'HTTP {response.status_code}'}", status=status
        )
    return data
