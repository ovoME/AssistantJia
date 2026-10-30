"""管理密钥和由可信登录端签发的读者短期令牌；HTTP 不能直接信任 reader_id。"""
import base64
import hashlib
import hmac
import json
import time
from contextvars import ContextVar

from fastapi import Header, HTTPException
from app.config import settings

active_reader = ContextVar("active_reader", default=None)


def sign_reader_token(reader_id, secret, expires_at):
    if not reader_id or not isinstance(reader_id, str) or len(secret) < 32:
        raise ValueError("读者必须为非空文本，签名密钥至少 32 字符。")
    raw = json.dumps({"sub": reader_id, "exp": expires_at}, separators=(",", ":")).encode()
    payload = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return payload + "." + signature


def reader_identity(authorization: str | None = Header(None)):
    if not authorization:
        return None
    if not settings.READER_TOKEN_SECRET or len(settings.READER_TOKEN_SECRET) < 32:
        raise HTTPException(503, "读者认证尚未配置。")
    try:
        if len(authorization) > 2100:
            raise ValueError()
        scheme, token = authorization.split(" ", 1)
        payload, signature = token.split(".")
        expected = hmac.new(settings.READER_TOKEN_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if scheme.lower() != "bearer" or len(token) > 2048 or not hmac.compare_digest(signature, expected):
            raise ValueError()
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if (not isinstance(claims, dict) or not isinstance(claims.get("sub"), str) or not claims["sub"] or
                isinstance(claims.get("exp"), bool) or not isinstance(claims.get("exp"), (int, float)) or
                not time.time() < claims["exp"] < time.time() + 86400 * 31):
            raise ValueError()
        return claims["sub"]
    except (ValueError, KeyError, TypeError, UnicodeError):
        raise HTTPException(401, "读者凭证无效或已过期。") from None


def resolve_reader(requested, authenticated):
    if requested and requested != authenticated:
        raise HTTPException(401 if authenticated is None else 403, "请使用本人已认证身份访问个性化数据。")
    return authenticated


def require_admin(x_admin_token: str | None = Header(None)):
    if not settings.ADMIN_TOKEN or len(settings.ADMIN_TOKEN) < 16:
        raise HTTPException(503, "管理端访问密钥尚未配置。")
    if not x_admin_token or not hmac.compare_digest(x_admin_token.encode(), settings.ADMIN_TOKEN.encode()):
        raise HTTPException(401, "请输入有效的管理端访问密钥。")


def ensure_reader(reader_id, allow_demo=False):
    if active_reader.get() != reader_id and not (allow_demo and settings.OPAC_PROVIDER == "demo" and reader_id == "demo-reader"):
        raise PermissionError("不能通过工具参数读取其他读者的个人数据。")
