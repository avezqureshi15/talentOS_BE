import time

import jwt

from app.core.config import settings
from app.core.keys import get_private_key_pem


def create_service_token() -> str:
    payload = {
        "iss": settings.SERVICE_NAME,
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
    }
    return jwt.encode(payload, get_private_key_pem(), algorithm="RS256")
