"""
Shared JWT + password-hashing helpers.

Added in Phase 6 — not part of the original scaffold. dashboard_routes.py
(REST) and websocket.py (WS handshake) both need to verify the same JWT,
so this factors that logic into one place rather than duplicating it —
the same "factor shared logic" pattern channels/common.py already
established for the three webhook adapters in Phase 5.

Requires two packages NOT yet confirmed to be in requirements.txt:
    pyjwt
    bcrypt
Add them (`pip install pyjwt bcrypt` / add to requirements.txt) before
running this phase.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import settings

JWT_ALGORITHM = "HS256"

# auto_error=False so a missing header raises our own 401 (with a
# consistent error body) instead of FastAPI's default.
_bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed/legacy hash stored — treat as a failed check, not a 500.
        return False


def create_access_token(*, staff_id: str, business_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": staff_id,
        "business_id": business_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError (or a subclass) on any invalid/expired token.
    Callers decide how to turn that into an HTTP 401 vs. a WS close code."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])


async def get_current_staff(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """
    FastAPI dependency for REST routes: `staff: dict = Depends(get_current_staff)`.

    Returns the decoded JWT payload (`sub` = staff id, `business_id`,
    `role`). Every dashboard route except /api/auth/login depends on this
    and MUST scope its query by staff["business_id"] — the same
    trust-boundary rule tools/order_tools.py applies to the bot
    (identity from trusted context, never from the caller's free-form
    input), applied here to staff instead of the LLM.
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        return decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )