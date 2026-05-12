"""
Base HTTP client with retry + timeout + structured logging.
All service clients inherit from this.
"""
from __future__ import annotations
import time
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from ..core.config import HTTP_TIMEOUT, HTTP_MAX_RETRY

logger = logging.getLogger(__name__)


def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=HTTP_MAX_RETRY,
        backoff_factor=0.4,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


_SESSION = _build_session()


def _extract_list(data: dict | list | None) -> list:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    for key in ("results", "books", "orders", "comments", "data", "products"):
        if isinstance(data.get(key), list):
            return data[key]
    return []


class ServiceClient:
    """Thin HTTP client with retry, timeout, and structured logging."""

    def __init__(self, base_url: str, service_name: str):
        self.base_url     = base_url.rstrip("/")
        self.service_name = service_name

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json:   dict | None = None,
        timeout: float = HTTP_TIMEOUT,
    ) -> dict | list | None:
        url = f"{self.base_url}{path}"
        t0  = time.monotonic()
        try:
            resp = _SESSION.request(
                method, url, params=params, json=json, timeout=timeout
            )
            elapsed = round((time.monotonic() - t0) * 1000)
            logger.debug("[%s] %s %s → %d (%dms)", self.service_name, method, path, resp.status_code, elapsed)
            if resp.status_code >= 400:
                logger.warning("[%s] %s %s returned %d", self.service_name, method, path, resp.status_code)
                return None
            return resp.json()
        except requests.Timeout:
            logger.error("[%s] %s %s timed out after %.1fs", self.service_name, method, path, timeout)
            return None
        except requests.RequestException as exc:
            logger.error("[%s] %s %s failed: %s", self.service_name, method, path, exc)
            return None

    def get(self, path: str, params: dict | None = None) -> dict | list | None:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict | None = None) -> dict | list | None:
        return self._request("POST", path, json=json)
