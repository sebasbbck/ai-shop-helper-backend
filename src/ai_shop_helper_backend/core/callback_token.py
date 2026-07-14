import hashlib
import hmac
from uuid import UUID

from ai_shop_helper_backend.core.config import settings


def make_callback_token(run_id: UUID, step_id: UUID) -> str:
    key = settings.SECRET_KEY.encode()
    message = f"{run_id}:{step_id}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def verify_callback_token(run_id: UUID, step_id: UUID, token: str) -> bool:
    expected = make_callback_token(run_id, step_id)
    return hmac.compare_digest(expected, token)
