import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

import database
import models

load_dotenv()

SECRET_KEY = os.getenv("GUARDDROP_SECRET_KEY", "guarddrop-dev-secret-change-me")
ACCESS_TOKEN_TTL_SECONDS = int(os.getenv("GUARDDROP_TOKEN_TTL_SECONDS", str(60 * 60 * 24 * 7)))

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(value: str) -> str:
    digest = hmac.new(SECRET_KEY.encode("utf-8"), value.encode("ascii"), hashlib.sha256).digest()
    return _b64url_encode(digest)


def create_access_token(user_id: int) -> str:
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8"))
    issued_at = int(time.time())
    payload = _b64url_encode(
        json.dumps(
            {
                "sub": user_id,
                "iat": issued_at,
                "exp": issued_at + ACCESS_TOKEN_TTL_SECONDS,
                "type": "access",
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    signing_input = f"{header}.{payload}"
    signature = _sign(signing_input)
    return f"{signing_input}.{signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header_segment, payload_segment, signature = token.split(".")
    except ValueError as exc:
        raise _unauthorized_exception() from exc

    expected_signature = _sign(f"{header_segment}.{payload_segment}")
    if not hmac.compare_digest(signature, expected_signature):
        raise _unauthorized_exception()

    try:
        payload = json.loads(_b64url_decode(payload_segment))
    except (json.JSONDecodeError, ValueError) as exc:
        raise _unauthorized_exception() from exc

    if payload.get("type") != "access":
        raise _unauthorized_exception()

    if int(payload.get("exp", 0)) <= int(time.time()):
        raise _unauthorized_exception()

    subject = payload.get("sub")
    if not isinstance(subject, int):
        raise _unauthorized_exception()

    return payload


def _get_user_for_token(token: str, db: Session) -> models.User:
    payload = decode_access_token(token)
    user = db.query(models.User).filter(models.User.id == payload["sub"]).first()
    if not user:
        raise _unauthorized_exception()
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(database.get_db),
) -> models.User:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise _unauthorized_exception()
    return _get_user_for_token(credentials.credentials, db)


def get_websocket_user(websocket: WebSocket, db: Session) -> models.User:
    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    else:
        token = websocket.query_params.get("token")

    if not token:
        raise _unauthorized_exception()

    return _get_user_for_token(token, db)
