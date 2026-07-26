from fastapi import APIRouter

from app.core.keys import get_public_key_pem

router = APIRouter()


@router.get("/.well-known/jwks.json")
def jwks():
    return {"publicKey": get_public_key_pem()}
