from io import BytesIO

import httpx
from pypdf import PdfReader

from app.common.clients.base_client import BaseClient, ClientError
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class ResumeClientError(ClientError):
    """Raised when resume download fails."""


class ResumeClient(BaseClient):
    """Downloads and extracts text from resume PDFs.

    Not a traditional API client — the URL is dynamic (Supabase Storage).
    We reuse :class:`BaseClient` for its retry/error machinery.
    """

    def __init__(self) -> None:
        super().__init__(base_url="", timeout=30, max_retries=2)

    @property
    def _service_name(self) -> str:
        return "Resume Storage"

    def download_bytes(self, resume_url: str) -> bytes:
        """Download raw PDF bytes from *resume_url*."""
        headers = {}
        if settings.SUPABASE_SERVICE_ROLE_KEY:
            headers["Authorization"] = f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}"

        try:
            response = self.sync.get(resume_url, headers=headers)
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as exc:
            raise ResumeClientError(
                message=f"Resume download failed: {exc}",
                status_code=getattr(exc.response, "status_code", 502) if hasattr(exc, "response") else 502,
            ) from exc

    def extract_text(self, resume_url: str) -> str:
        """Download a resume PDF and extract its text content."""
        content = self.download_bytes(resume_url)
        try:
            reader = PdfReader(BytesIO(content))
            return "".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            logger.warning("PDF parse error for %s: %s", resume_url, exc)
            return ""

    # Unused abstract override — kept for completeness
    def _map_error(self, exc: Exception) -> Exception:
        return ResumeClientError(str(exc))
