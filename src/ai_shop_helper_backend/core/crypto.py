import base64
import hashlib

from ai_shop_helper_backend.core.config import settings


def _fernet():
    from cryptography.fernet import Fernet

    digest = hashlib.sha256(settings.CRYPTOGRAPHIC_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
