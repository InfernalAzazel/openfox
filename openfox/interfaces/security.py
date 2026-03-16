import os
from fastapi import Request
from fastapi.responses import Response
from lark_oapi.core.model import RawRequest, RawResponse
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.core.const import UTF_8
from fastapi.responses import Response
from openfox.tools.config import ConfigTools

config_tools = ConfigTools()
config = config_tools.load()

# ---------- 飞书事件订阅（lark_oapi）----------
# https://open.feishu.cn/document/server-side-sdk/python--sdk/handle-callbacks#335ab2f1

def get_feishu_verification_token() -> str:
    """
    从环境变量读取飞书应用的 Verification Token（事件订阅 > 请求地址配置）。
    生产环境下未设置则抛出 ValueError；开发环境下未设置则返回空字符串以便本地调试。
    """
    token = config.channels.feishu.verification_token
    if not token:
        raise ValueError("在生产模式下未设置 feishu 的 verification_token")
    return token


def get_feishu_encrypt_key() -> str:
    """
    从环境变量读取飞书应用的 Encrypt Key（可选，配置请求体加密时必填）。
    未设置时返回空字符串（表示未启用加密）。
    """
    key = config.channels.feishu.encrypt_key
    if not key:
        raise ValueError("在生产模式下未设置 feishu 的 encrypt_key")
    return key


# lark_oapi 签名校验依赖的 header 名（FastAPI/ASGI 可能转成小写）
_LARK_HEADER_KEYS = (
    "X-Lark-Request-Timestamp",
    "X-Lark-Request-Nonce",
    "X-Lark-Signature",
)


def _normalize_lark_headers(headers: dict) -> dict:
    """确保飞书签名所需的 header 使用规范 key。"""
    out = dict(headers)
    for key in _LARK_HEADER_KEYS:
        if key not in out:
            val = next((v for k, v in headers.items() if k.lower() == key.lower()), None)
            if val is not None:
                out[key] = val
    return out


def build_feishu_event_handler():
    """
    使用 lark_oapi 构建飞书事件回调处理器（含 URL 验证、解密、token 校验与事件分发）。
    见：https://open.feishu.cn/document/server-side-sdk/python--sdk/handle-callbacks#335ab2f1
    """
    encrypt_key = get_feishu_encrypt_key()
    verification_token = get_feishu_verification_token()
    return EventDispatcherHandler.builder(encrypt_key, verification_token).build()


def feishu_handle_callback(uri: str, body: bytes, headers: dict) -> "RawResponse":
    """
    使用 lark_oapi 处理飞书事件回调（含 url_verification、解密、token 校验）。
    由调用方先读取请求 body 与 headers，再传入，便于在 async 路由中 await request.body()。
    """
    raw = RawRequest()
    raw.uri = uri
    raw.body = body
    raw.headers = _normalize_lark_headers(headers)
    return build_feishu_event_handler().do(raw)


async def feishu_raw_request(request: "Request") -> "RawRequest":
    """从 FastAPI Request 构建 lark_oapi RawRequest（含飞书签名用 header 规范化）。"""
    req = RawRequest()
    req.uri = request.url.path
    req.body = await request.body()
    req.headers = _normalize_lark_headers(dict(request.headers))
    return req


def feishu_raw_response(raw: "RawResponse") -> "Response":
    """将 lark_oapi RawResponse 转为 FastAPI Response。"""
    content = raw.content or b""
    body = (
        content
        if isinstance(content, bytes)
        else (content.encode(UTF_8) if isinstance(content, str) else b"")
    )
    return Response(
        content=body,
        status_code=raw.status_code or 200,
        headers=raw.headers,
    )