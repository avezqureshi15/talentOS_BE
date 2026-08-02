import hmac

import jwt
import httpx
from fastapi import Header, HTTPException

from app.core.config import settings
from app.core.secrets import get_secret

key_cache: dict[str, str] = {}

PEER_JWKS: dict[str, str] = {}
if settings.JWKS_URL_AI_RECRUITMENT_POC:
    PEER_JWKS["ai-recruitment-poc"] = settings.JWKS_URL_AI_RECRUITMENT_POC


async def get_public_key(issuer: str) -> str:
    if issuer in key_cache:
        return key_cache[issuer]
    url = PEER_JWKS.get(issuer)
    if not url:
        raise HTTPException(status_code=401, detail=f"Unknown issuer: {issuer}")
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        data = response.json()
    key_cache[issuer] = data["publicKey"]
    return data["publicKey"]


async def verify_service_jwt(authorization: str | None = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No service token provided")

    token = authorization.split(" ")[1]

    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        if "iss" not in decoded:
            raise HTTPException(status_code=401, detail="Invalid service token: no issuer")

        public_key = await get_public_key(decoded["iss"])
        jwt.decode(token, public_key, algorithms=["RS256"])
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid service token signature")


def verify_service_api_key(authorization: str | None = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No service token provided")
    token = authorization.split(" ")[1]
    expected = get_secret("SERVICE_API_KEY")
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid service API key")
    return token
