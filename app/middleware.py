from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings


class GitlabTokenMiddleware(BaseHTTPMiddleware):
    """Rejects GitLab webhook requests that don't carry the configured secret token."""

    PROTECTED_PATHS = {"/webhook/gitlab"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.PROTECTED_PATHS:
            secret = request.query_params.get("secret", "")
            if secret != settings.GITLAB_WEBHOOK_SECRET:
                return JSONResponse(
                    {"detail": "Invalid webhook secret"}, status_code=401
                )
        return await call_next(request)
