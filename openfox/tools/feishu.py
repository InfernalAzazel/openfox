import io
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import unquote, urlparse

import httpx
import lark_oapi as lark
from agno.tools import Toolkit
from agno.utils.log import logger
from lark_oapi.api.im.v1 import (
    CreateFileRequest,
    CreateFileRequestBody,
    CreateImageRequest,
    CreateImageRequestBody,
    CreateMessageRequest,
    CreateMessageRequestBody,
)

from openfox.tools.config import ConfigTools


class FeiShuTools(Toolkit):
    """Async toolkit for sending Feishu messages and media."""

    def __init__(self, **kwargs: Any):
        """Initialize Feishu client and register async toolkit methods.

        Args:
            **kwargs: Extra toolkit options forwarded to `Toolkit`.
        """
        self.config_tools = ConfigTools()
        self.config = self.config_tools.load()
        self.app_id = self.config.channels.feishu.app_id
        self.app_secret = self.config.channels.feishu.app_secret
        self.client = (
            lark.Client.builder()
            .app_id(self.app_id)
            .app_secret(self.app_secret)
            .build()
        )
        async_tools: List[tuple[Callable[..., Any], str]] = [
            (self.send_text_message, "send_text_message"),
            (self.send_image_message, "send_image_message"),
            (self.send_file_message, "send_file_message"),
            (self.send_audio_message, "send_audio_message"),
            (self.send_media_message, "send_media_message"),
        ]
        super().__init__(name="feishu", async_tools=async_tools, **kwargs)

    @staticmethod
    def _source_is_http_url(source: str) -> bool:
        """Check whether a source string is an HTTP/HTTPS URL.

        Args:
            source: URL or local path string.

        Returns:
            True if `source` starts with `http://` or `https://`.
        """
        s = source.strip().lower()
        return s.startswith("http://") or s.startswith("https://")

    async def _load_bytes_from_source(self, source: str) -> bytes:
        """Load bytes from a URL or local file path.

        Args:
            source: URL or local path.

        Returns:
            Raw bytes from the source.

        Raises:
            FileNotFoundError: If local file does not exist.
            httpx.HTTPError: If URL fetch fails.
        """
        if self._source_is_http_url(source):
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=httpx.Timeout(60.0)
            ) as http:
                resp = await http.get(source.strip())
                resp.raise_for_status()
                return resp.content

        path = Path(source).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        return path.read_bytes()

    @staticmethod
    def _default_file_name_from_url(url: str) -> str:
        """Extract a default file name from URL path.

        Args:
            url: Source URL.

        Returns:
            Final path segment or `file.bin` as fallback.
        """
        path = urlparse(url.strip()).path
        name = unquote(path.rsplit("/", 1)[-1]) if path else ""
        return name or "file.bin"

    @staticmethod
    def _infer_feishu_file_type(file_name: str) -> str:
        """Infer Feishu `file_type` from file extension.

        Args:
            file_name: File name with extension.

        Returns:
            Feishu file type string (defaults to `stream`).
        """
        ext = Path(file_name).suffix.lower()
        mapping = {
            ".pdf": "pdf",
            ".doc": "doc",
            ".xls": "xls",
            ".ppt": "ppt",
            ".mp4": "mp4",
            ".opus": "opus",
        }
        return mapping.get(ext, "stream")

    def _resolve_upload_file_name(self, source: str, file_name: Optional[str]) -> str:
        """Resolve upload file name.

        Args:
            source: URL or local path.
            file_name: Optional override name.

        Returns:
            Final upload file name.
        """
        if file_name and file_name.strip():
            return file_name.strip()
        if self._source_is_http_url(source):
            return self._default_file_name_from_url(source)
        return Path(source).expanduser().name

    async def _upload_image_get_key(self, image_bytes: bytes) -> str:
        """Upload image bytes and return Feishu `image_key`.

        Args:
            image_bytes: Image content bytes.

        Returns:
            Uploaded image key.

        Raises:
            RuntimeError: If upload fails or no image key is returned.
        """
        stream = io.BytesIO(image_bytes)
        stream.seek(0)
        img_body = (
            CreateImageRequestBody.builder()
            .image_type("message")
            .image(stream)
            .build()
        )
        img_req = CreateImageRequest.builder().request_body(img_body).build()
        img_resp = await self.client.im.v1.image.acreate(img_req)
        if not img_resp.success():
            logger.error(f"Feishu image upload failed: code={img_resp.code}, msg={img_resp.msg}")
            raise RuntimeError(f"Feishu image upload error: {img_resp.msg}")
        key = getattr(img_resp.data, "image_key", None) if img_resp.data else None
        if not key:
            raise RuntimeError("Feishu image upload returned no image_key")
        return key

    async def _upload_file_get_key(
        self,
        data: bytes,
        *,
        file_name: str,
        file_type: str,
        duration_ms: Optional[int] = None,
    ) -> str:
        """Upload file bytes and return Feishu `file_key`.

        Args:
            data: File bytes.
            file_name: Upload file name.
            file_type: Feishu file type.
            duration_ms: Optional duration for audio/video.

        Returns:
            Uploaded file key.

        Raises:
            ValueError: If file is empty or exceeds size limit.
            RuntimeError: If upload fails or no file key is returned.
        """
        if not data:
            raise ValueError("File is empty; Feishu does not accept empty uploads")
        max_bytes = 30 * 1024 * 1024
        if len(data) > max_bytes:
            raise ValueError(f"File exceeds Feishu limit ({max_bytes // (1024 * 1024)} MB)")
        stream = io.BytesIO(data)
        stream.seek(0)
        body_b = (
            CreateFileRequestBody.builder()
            .file_type(file_type)
            .file_name(file_name)
            .file(stream)
        )
        if duration_ms is not None:
            body_b = body_b.duration(duration_ms)
        body = body_b.build()
        req = CreateFileRequest.builder().request_body(body).build()
        file_resp = await self.client.im.v1.file.acreate(req)
        if not file_resp.success():
            logger.error(f"Feishu file upload failed: code={file_resp.code}, msg={file_resp.msg}")
            raise RuntimeError(f"Feishu file upload error: {file_resp.msg}")
        key = getattr(file_resp.data, "file_key", None) if file_resp.data else None
        if not key:
            raise RuntimeError("Feishu file upload returned no file_key")
        return key

    async def _acreate_message(
        self,
        *,
        receive_id: str,
        receive_id_type: str,
        msg_type: str,
        payload: Dict[str, Any],
    ):
        """Create a Feishu message using an already-built payload.

        Args:
            receive_id: Target user/chat id.
            receive_id_type: Feishu receive id type.
            msg_type: Feishu message type.
            payload: Message body payload.

        Returns:
            Feishu API response data.

        Raises:
            RuntimeError: If message creation fails.
        """
        body = (
            CreateMessageRequestBody.builder()
            .receive_id(receive_id)
            .msg_type(msg_type)
            .content(json.dumps(payload, ensure_ascii=False))
            .build()
        )
        req = (
            CreateMessageRequest.builder()
            .receive_id_type(receive_id_type)
            .request_body(body)
            .build()
        )
        resp = await self.client.im.v1.message.acreate(req)
        if not resp.success():
            logger.error(f"Feishu send failed: code={resp.code}, msg={resp.msg}")
            raise RuntimeError(f"Feishu API error: {resp.msg}")
        return resp.data

    async def send_text_message(
        self,
        receive_id: str,
        content: Any,
        receive_id_type: str = "user_id",
        use_markdown: bool = False,
        italics: bool = False,
    ):
        """Send a text message.

        Args:
            receive_id: Target user/chat id.
            content: Raw text or prebuilt payload dict.
            receive_id_type: Feishu receive id type.
            use_markdown: Whether to send as interactive markdown card.
            italics: Whether to wrap each line with markdown italics.

        Returns:
            Feishu API response data.
        """
        if isinstance(content, dict):
            payload = content
            real_type = "text"
        else:
            text = str(content or "")
            if italics:
                text = "\n".join(f"_{line}_" for line in text.split("\n"))
            if use_markdown:
                payload = {
                    "schema": "2.0",
                    "body": {"elements": [{"tag": "markdown", "content": text}]},
                }
                real_type = "interactive"
            else:
                payload = {"text": text}
                real_type = "text"
        return await self._acreate_message(
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            msg_type=real_type,
            payload=payload,
        )

    async def send_image_message(
        self,
        receive_id: str,
        content: Any,
        receive_id_type: str = "user_id",
    ):
        """Send an image message.

        Args:
            receive_id: Target user/chat id.
            content: `{"image_key": ...}` or URL/path to image source.
            receive_id_type: Feishu receive id type.

        Returns:
            Feishu API response data.
        """
        if isinstance(content, dict):
            payload = content
        else:
            image_bytes = await self._load_bytes_from_source(str(content))
            image_key = await self._upload_image_get_key(image_bytes)
            payload = {"image_key": image_key}
        return await self._acreate_message(
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            msg_type="image",
            payload=payload,
        )

    async def send_file_message(
        self,
        receive_id: str,
        content: Any,
        receive_id_type: str = "user_id",
        file_name: Optional[str] = None,
        file_type: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ):
        """Send a generic file message.

        Args:
            receive_id: Target user/chat id.
            content: `{"file_key": ...}` or URL/path to file source.
            receive_id_type: Feishu receive id type.
            file_name: Optional upload name override.
            file_type: Optional Feishu file type override.
            duration_ms: Optional duration for media-like files.

        Returns:
            Feishu API response data.
        """
        if isinstance(content, dict):
            payload = content
        else:
            source = str(content)
            data = await self._load_bytes_from_source(source)
            name = self._resolve_upload_file_name(source, file_name)
            resolved_file_type = (
                file_type.strip()
                if file_type and file_type.strip()
                else self._infer_feishu_file_type(name)
            )
            file_key = await self._upload_file_get_key(
                data,
                file_name=name,
                file_type=resolved_file_type,
                duration_ms=duration_ms,
            )
            payload = {"file_key": file_key}
        return await self._acreate_message(
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            msg_type="file",
            payload=payload,
        )

    async def send_audio_message(
        self,
        receive_id: str,
        content: Any,
        receive_id_type: str = "user_id",
        file_name: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ):
        """Send an audio message.

        Args:
            receive_id: Target user/chat id.
            content: `{"file_key": ...}` or URL/path to audio source.
            receive_id_type: Feishu receive id type.
            file_name: Optional upload name override (must end with `.opus`).
            duration_ms: Optional audio duration.

        Returns:
            Feishu API response data.

        Raises:
            ValueError: If audio extension is not `.opus`.
        """
        if isinstance(content, dict):
            payload = content
        else:
            source = str(content)
            data = await self._load_bytes_from_source(source)
            name = self._resolve_upload_file_name(source, file_name)
            if Path(name).suffix.lower() != ".opus":
                raise ValueError("Feishu voice requires an OPUS file: filename must end with .opus")
            file_key = await self._upload_file_get_key(
                data,
                file_name=name,
                file_type="opus",
                duration_ms=duration_ms,
            )
            payload = {"file_key": file_key}
        return await self._acreate_message(
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            msg_type="audio",
            payload=payload,
        )

    async def send_media_message(
        self,
        receive_id: str,
        content: Any,
        receive_id_type: str = "user_id",
        file_name: Optional[str] = None,
        duration_ms: Optional[int] = None,
        thumbnail: Optional[str] = None,
    ):
        """Send a media (video) message.

        Args:
            receive_id: Target user/chat id.
            content: `{"file_key": ...}` or URL/path to video source.
            receive_id_type: Feishu receive id type.
            file_name: Optional upload name override (must end with `.mp4`).
            duration_ms: Optional video duration.
            thumbnail: Optional thumbnail URL/path.

        Returns:
            Feishu API response data.

        Raises:
            ValueError: If video extension is not `.mp4`.
        """
        if isinstance(content, dict):
            payload = content
        else:
            source = str(content)
            data = await self._load_bytes_from_source(source)
            name = self._resolve_upload_file_name(source, file_name)
            if Path(name).suffix.lower() != ".mp4":
                raise ValueError("Feishu video requires an MP4 file: filename must end with .mp4")
            file_key = await self._upload_file_get_key(
                data,
                file_name=name,
                file_type="mp4",
                duration_ms=duration_ms,
            )
            payload = {"file_key": file_key}
            if thumbnail and thumbnail.strip():
                thumb_bytes = await self._load_bytes_from_source(thumbnail.strip())
                payload["image_key"] = await self._upload_image_get_key(thumb_bytes)
        return await self._acreate_message(
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            msg_type="media",
            payload=payload,
        )