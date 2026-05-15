"""Async HTTP client for the FastAPI split service."""
import httpx

SERVICE_URL = 'http://127.0.0.1:8001'
REQUEST_TIMEOUT = 30.0  # seconds


class ServiceClient:
    """Async client wrapping the /health and /api/split endpoints."""

    def __init__(self, base_url: str = SERVICE_URL):
        self.base_url = base_url

    async def health(self) -> bool:
        """Check if the service is reachable. Returns True/False."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f'{self.base_url}/health')
                return r.status_code == 200
        except Exception:
            return False

    async def split(self, text: str, params: dict | None = None) -> dict:
        """Send text to /api/split, return parsed JSON response.

        Raises ServiceError on non-200 response or network failure.
        """
        body = {
            'text': text,
            'params': params or {},
        }
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.post(
                f'{self.base_url}/api/split',
                json=body,
            )
        if r.status_code == 422:
            detail = r.json().get('detail', '文本无法解析')
            raise ServiceError(detail, status_code=422)
        if r.status_code != 200:
            raise ServiceError(
                f'服务返回错误 ({r.status_code})',
                status_code=r.status_code)
        return r.json()


class ServiceError(Exception):
    """Raised when the service returns an error response."""
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


# Module-level singleton
client = ServiceClient()
