import time
from typing import Dict, List
from fastapi import Request, HTTPException, status

class InMemoryRateLimiter:
    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self._history: Dict[str, List[float]] = {}

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        minute_ago = now - 60.0

        if client_ip not in self._history:
            self._history[client_ip] = []

        # Remove requests older than 1 minute
        self._history[client_ip] = [ts for ts in self._history[client_ip] if ts > minute_ago]

        if len(self._history[client_ip]) >= self.requests_per_minute:
            return False

        self._history[client_ip].append(now)
        return True

# 10 requests per minute per IP for OCR endpoint
ocr_rate_limiter = InMemoryRateLimiter(requests_per_minute=10)

async def check_ocr_rate_limit(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not ocr_rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many OCR requests. Please retry later."
                }
            }
        )
