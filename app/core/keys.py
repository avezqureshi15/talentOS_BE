from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

KEYS_DIR = Path(__file__).resolve().parent.parent.parent / "keys"
PRIV_PATH = KEYS_DIR / "private.pem"
PUB_PATH = KEYS_DIR / "public.pem"


def _load_or_generate_keys():
    if PRIV_PATH.exists() and PUB_PATH.exists():
        with open(PRIV_PATH) as f:
            private_key_pem = f.read()
        with open(PUB_PATH) as f:
            public_key_pem = f.read()
        return private_key_pem, public_key_pem

    KEYS_DIR.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    private_key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    public_key_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    with open(PRIV_PATH, "w") as f:
        f.write(private_key_pem)
    with open(PUB_PATH, "w") as f:
        f.write(public_key_pem)

    return private_key_pem, public_key_pem


_PRIVATE_KEY, PUBLIC_KEY = _load_or_generate_keys()


def get_public_key_pem() -> str:
    return PUBLIC_KEY


def get_private_key_pem() -> str:
    return _PRIVATE_KEY
