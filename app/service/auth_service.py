import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.database.connection import get_db
from app.database.models import AuthSessionModel, PatientProfileModel, SysUserModel
from app.exceptions import ServiceException
from app.security.jwt import decode_token, encode_token
from app.service.session_store import delete_session, put_session, validate_session

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    role: str
    session_id: str


def _normalize_db_time(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _exchange_wechat_code(code: str) -> str:
    if settings.allow_dev_login and (not settings.wx_appid or code.startswith("dev-")):
        return "dev_" + hashlib.sha256(code.encode("utf-8")).hexdigest()
    if not settings.wx_appid or not settings.wx_secret:
        raise ServiceException("微信登录尚未配置", 40007, 503)
    response = httpx.get(
        "https://api.weixin.qq.com/sns/jscode2session",
        params={
            "appid": settings.wx_appid,
            "secret": settings.wx_secret,
            "js_code": code,
            "grant_type": "authorization_code",
        },
        timeout=8,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("errcode") or not result.get("openid"):
        raise ServiceException("微信登录凭证无效", 40007, 400)
    return result["openid"]


def login_with_wechat(db: Session, code: str) -> dict:
    if not code.strip():
        raise ServiceException("code 不能为空", 40001, 400)
    openid = _exchange_wechat_code(code.strip())
    user = db.query(SysUserModel).filter(SysUserModel.openid == openid).one_or_none()
    if user is None:
        user = SysUserModel(openid=openid, role="patient", status="active")
        db.add(user)
        db.flush()
        db.add(PatientProfileModel(user_id=user.user_id))
    if user.status != "active":
        raise ServiceException("账号已停用", 40003, 403)

    now = datetime.now(timezone.utc)
    session_id = str(uuid4())
    expires_at = now + timedelta(minutes=settings.jwt_expire_minutes)
    db.add(AuthSessionModel(session_id=session_id, user_id=user.user_id, expires_at=expires_at))
    db.commit()
    put_session(session_id, user.user_id, settings.jwt_expire_minutes * 60)
    token = encode_token(
        {
            "sub": user.user_id,
            "session_id": session_id,
            "iat": int(time.time()),
            "exp": int(expires_at.timestamp()),
        },
        settings.jwt_secret_key,
    )
    return {"access_token": token, "token_type": "bearer", "expires_at": expires_at.isoformat()}


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ServiceException("请先登录", 40002, 401)
    payload = decode_token(credentials.credentials, settings.jwt_secret_key)
    session = db.get(AuthSessionModel, payload["session_id"])
    if session is None or session.revoked_at is not None:
        raise ServiceException("登录已失效，请重新登录", 40002, 401)
    if _normalize_db_time(session.expires_at) <= datetime.now(timezone.utc):
        raise ServiceException("登录已过期，请重新登录", 40002, 401)
    user = db.get(SysUserModel, payload["sub"])
    if user is None or user.status != "active" or user.deleted_at is not None:
        raise ServiceException("账号不可用", 40002, 401)
    validate_session(session.session_id, user.user_id, settings.jwt_expire_minutes * 60)
    return CurrentUser(user_id=user.user_id, role=user.role, session_id=session.session_id)


def logout(db: Session, current_user: CurrentUser) -> None:
    session = db.get(AuthSessionModel, current_user.session_id)
    if session and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()
    delete_session(current_user.session_id)
