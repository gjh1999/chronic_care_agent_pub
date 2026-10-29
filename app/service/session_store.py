import json

from app.config.settings import settings
from app.exceptions import ServiceException


def _client():
    if not settings.redis_url:
        return None
    try:
        import redis

        return redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=2)
    except Exception as exc:
        if settings.app_env == "prod":
            raise ServiceException("会话服务不可用", 50010, 503) from exc
        return None


def put_session(session_id: str, user_id: str, ttl_seconds: int) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.setex(f"access_token:{session_id}", ttl_seconds, json.dumps({"user_id": user_id}))
    except Exception as exc:
        if settings.app_env == "prod":
            raise ServiceException("会话服务不可用", 50010, 503) from exc


def validate_session(session_id: str, user_id: str, ttl_seconds: int) -> None:
    client = _client()
    if client is None:
        return
    try:
        key = f"access_token:{session_id}"
        raw = client.get(key)
        if not raw or json.loads(raw).get("user_id") != user_id:
            raise ServiceException("登录已失效，请重新登录", 40002, 401)
        client.expire(key, ttl_seconds)
    except ServiceException:
        raise
    except Exception as exc:
        if settings.app_env == "prod":
            raise ServiceException("会话服务不可用", 50010, 503) from exc


def delete_session(session_id: str) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.delete(f"access_token:{session_id}")
    except Exception as exc:
        if settings.app_env == "prod":
            raise ServiceException("会话服务不可用", 50010, 503) from exc
