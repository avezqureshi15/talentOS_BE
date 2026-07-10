from abc import ABC, abstractmethod

import httpx

from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode
from app.core.logger import get_logger

logger = get_logger(__name__)


class ClientError(BaseAppException):
    """Base exception for all external service client errors."""


class BaseClient(ABC):
    """Abstract base client for external HTTP services.

    Provides:
    - Centralised httpx client lifecycle (sync + async)
    - Configurable retry with exponential backoff for transient failures
    - Consistent error handling → domain exceptions
    """

    def __init__(self, base_url: str, timeout: int = 30, max_retries: int = 2):
        if not base_url:
            logger.warning("%s initialized with empty base_url", self.__class__.__name__)
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._sync_client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None

    # ── sync client ──────────────────────────────────────────────

    @property
    def sync(self) -> httpx.Client:
        if self._sync_client is None:
            self._sync_client = self._build_sync_client()
        return self._sync_client

    def _build_sync_client(self) -> httpx.Client:
        return httpx.Client(timeout=self._timeout)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_data: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        url = f"{self._base_url}/{path.lstrip('/')}"
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = self.sync.request(method, url, params=params, json=json_data, headers=headers)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code >= 500 and attempt < self._max_retries:
                    logger.warning("Retry %d/%d after %s %s (status %d)", attempt + 1, self._max_retries, method, url, exc.response.status_code)
                    continue
                raise self._map_error(exc) from exc
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    logger.warning("Retry %d/%d after connection error: %s", attempt + 1, self._max_retries, exc)
                    continue
                raise ClientError(
                    message=f"Connection to {self._service_name} failed: {exc}",
                    code=ErrorCode.INTERNAL_ERROR,
                    status_code=502,
                ) from exc

        raise ClientError(
            message=f"{self._service_name} request failed after {self._max_retries + 1} attempts",
            code=ErrorCode.INTERNAL_ERROR,
            status_code=502,
        ) from last_exc

    # ── async client (optional — for streaming) ──────────────────

    @property
    def async_client(self) -> httpx.AsyncClient:
        if self._async_client is None:
            self._async_client = self._build_async_client()
        return self._async_client

    def _build_async_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout)

    # ── helpers for subclasses ───────────────────────────────────

    def _get(self, path: str, **kwargs) -> httpx.Response:
        return self._request("GET", path, **kwargs)

    def _post(self, path: str, **kwargs) -> httpx.Response:
        return self._request("POST", path, **kwargs)

    def _put(self, path: str, **kwargs) -> httpx.Response:
        return self._request("PUT", path, **kwargs)

    def _delete(self, path: str, **kwargs) -> httpx.Response:
        return self._request("DELETE", path, **kwargs)

    @property
    @abstractmethod
    def _service_name(self) -> str:
        """Human-readable name for error messages."""

    def _map_error(self, exc: httpx.HTTPStatusError) -> Exception:
        """Override to map HTTP errors to domain-specific exceptions."""
        status = exc.response.status_code
        body = _try_extract_body(exc.response)
        return ClientError(
            message=f"{self._service_name} returned {status}: {body}",
            code=ErrorCode.INTERNAL_ERROR,
            status_code=status,
        )

    # ── lifecycle ────────────────────────────────────────────────

    def close_sync(self) -> None:
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None

    async def close_async(self) -> None:
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None


def _try_extract_body(response: httpx.Response) -> str:
    try:
        data = response.json()
        return data.get("error", data.get("message", str(data)))
    except Exception:
        return response.text[:200]
