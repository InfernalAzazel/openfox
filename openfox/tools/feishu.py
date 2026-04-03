import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlparse
import httpx
from agno.tools import Toolkit
from agno.utils.log import logger
from lark_oapi import Client
from lark_oapi.api.im.v1.model.create_file_request import CreateFileRequest
from lark_oapi.api.im.v1.model.create_file_request_body import CreateFileRequestBody
from lark_oapi.api.im.v1.model.create_image_request import CreateImageRequest
from lark_oapi.api.im.v1.model.create_image_request_body import CreateImageRequestBody
from lark_oapi.api.im.v1.model.create_message_request import CreateMessageRequest
from lark_oapi.api.im.v1.model.create_message_request_body import CreateMessageRequestBody
from openfox.tools.config import ConfigTools


class FeishuTools(Toolkit):
    """Feishu (Lark) API toolkit: messaging helpers."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize Feishu tools from config."""
        self.config_tools = ConfigTools()
        self.config = self.config_tools.load()
        self.app_id = self.config.channels.feishu.app_id
        self.app_secret = self.config.channels.feishu.app_secret
        self.encrypt_key = self.config.channels.feishu.encrypt_key
        self.verification_token = self.config.channels.feishu.verification_token

        self.tools = [
            self.send_text_message,
            self.send_image_message,
            self.send_file_message,
            self.send_audio_message,
            self.send_video_message,
        ]

        super().__init__(name="feishu", tools=self.tools, **kwargs)

    def _get_client(self) -> Client:
        return Client.builder().app_id(self.app_id).app_secret(self.app_secret).build()

    @staticmethod
    def _source_is_http_url(source: str) -> bool:
        s = source.strip().lower()
        return s.startswith("http://") or s.startswith("https://")

    async def _load_bytes_from_source(self, source: str) -> bytes:
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
        path = urlparse(url.strip()).path
        name = unquote(path.rsplit("/", 1)[-1]) if path else ""
        return name or "file.bin"

    @staticmethod
    def _infer_feishu_file_type(file_name: str) -> str:
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
        if file_name and file_name.strip():
            return file_name.strip()
        if self._source_is_http_url(source):
            return self._default_file_name_from_url(source)
        return Path(source).expanduser().name

    async def _upload_image_get_key(self, client: Client, image_bytes: bytes) -> str:
        stream = io.BytesIO(image_bytes)
        stream.seek(0)
        img_body = (
            CreateImageRequestBody.builder()
            .image_type("message")
            .image(stream)
            .build()
        )
        img_req = CreateImageRequest.builder().request_body(img_body).build()
        img_resp = await client.im.v1.image.acreate(img_req)
        if not img_resp.success():
            logger.error(
                f"Feishu image upload failed: code={img_resp.code}, msg={img_resp.msg}"
            )
            raise RuntimeError(f"Feishu image upload error: {img_resp.msg}")
        key = getattr(img_resp.data, "image_key", None) if img_resp.data else None
        if not key:
            raise RuntimeError("Feishu image upload returned no image_key")
        return key

    async def _upload_file_get_key(
        self,
        client: Client,
        data: bytes,
        *,
        file_name: str,
        file_type: str,
        duration_ms: Optional[int] = None,
    ) -> str:
        if not data:
            raise ValueError("File is empty; Feishu does not accept empty uploads")
        max_bytes = 30 * 1024 * 1024
        if len(data) > max_bytes:
            raise ValueError(
                f"File exceeds Feishu limit ({max_bytes // (1024 * 1024)} MB)"
            )
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
        file_resp = await client.im.v1.file.acreate(req)
        if not file_resp.success():
            logger.error(
                f"Feishu file upload failed: code={file_resp.code}, msg={file_resp.msg}"
            )
            raise RuntimeError(f"Feishu file upload error: {file_resp.msg}")
        key = getattr(file_resp.data, "file_key", None) if file_resp.data else None
        if not key:
            raise RuntimeError("Feishu file upload returned no file_key")
        return key

    async def send_text_message(
        self,
        text: str = "",
        receive_id: Optional[str] = None,
        receive_id_type: str = "user_id",
        use_markdown: bool = True,
        italics: bool = False,
    ) -> str:
        """Send a message to a Feishu user or chat (async).

        If use_markdown is True, renders via card JSON v2 markdown element; otherwise plain text.
        If italics is True, wraps each line in Markdown italics (_line_).
        """
        if not receive_id:
            raise ValueError("receive_id is required")
        if italics:
            text = "\n".join(f"_{line}_" for line in text.split("\n"))
        if use_markdown:
            card: Dict[str, Any] = {
                "schema": "2.0",
                "body": {
                    "elements": [
                        {"tag": "markdown", "content": text},
                    ]
                },
            }
            msg_type = "interactive"
            content = json.dumps(card, ensure_ascii=False)
        else:
            msg_type = "text"
            content = json.dumps({"text": text}, ensure_ascii=False)
        client = self._get_client()
        body = (
            CreateMessageRequestBody.builder()
            .receive_id(receive_id)
            .msg_type(msg_type)
            .content(content)
            .build()
        )
        req = (
            CreateMessageRequest.builder()
            .receive_id_type(receive_id_type)
            .request_body(body)
            .build()
        )
        resp = await client.im.v1.message.acreate(req)
        if not resp.success():
            logger.error(f"Feishu send failed: code={resp.code}, msg={resp.msg}")
            raise RuntimeError(f"Feishu API error: {resp.msg}")
        msg_id = getattr(resp.data, "message_id", None) or "unknown"
        return f"Message sent. message_id: {msg_id}"

    async def send_image_message(
        self,
        image: str,
        receive_id: Optional[str] = None,
        receive_id_type: str = "user_id",
    ) -> str:
        """Send an image message (async).

        ``image`` may be:
        - A direct image URL starting with ``http://`` or ``https://``: downloaded first, then uploaded
          to Feishu;
        - Any other string: treated as a local file path (``~`` is expanded).

        The Feishu API requires an ``image_key``; both local files and URLs are uploaded via
        ``im/v1/images`` first.
        """
        if not image or not str(image).strip():
            raise ValueError("image is required")
        if not receive_id:
            raise ValueError("receive_id is required")
        image_bytes = await self._load_bytes_from_source(image)
        client = self._get_client()
        image_key = await self._upload_image_get_key(client, image_bytes)
        content = json.dumps({"image_key": image_key}, ensure_ascii=False)
        body = (
            CreateMessageRequestBody.builder()
            .receive_id(receive_id)
            .msg_type("image")
            .content(content)
            .build()
        )
        req = (
            CreateMessageRequest.builder()
            .receive_id_type(receive_id_type)
            .request_body(body)
            .build()
        )
        resp = await client.im.v1.message.acreate(req)
        if not resp.success():
            logger.error(f"Feishu send image failed: code={resp.code}, msg={resp.msg}")
            raise RuntimeError(f"Feishu API error: {resp.msg}")
        msg_id = getattr(resp.data, "message_id", None) or "unknown"
        return f"Image sent. message_id: {msg_id}"

    async def send_file_message(
        self,
        file: str,
        receive_id: Optional[str] = None,
        receive_id_type: str = "user_id",
        file_name: Optional[str] = None,
        file_type: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> str:
        """Send a file message (async): upload via ``im/v1/files``, then send as ``file``.

        ``file`` may be a URL (``http``/``https``) or a local path (``~`` expanded).

        ``file_name`` sets the display/name suffix for upload; if omitted, derived from path
        or URL. ``file_type`` overrides Feishu ``file_type`` (e.g. pdf, mp4); otherwise
        inferred from the filename extension, defaulting to ``stream``. Max size 30 MB.
        ``duration_ms`` is optional for audio/video (milliseconds).
        """
        if not file or not str(file).strip():
            raise ValueError("file is required")
        if not receive_id:
            raise ValueError("receive_id is required")
        data = await self._load_bytes_from_source(file)
        name = self._resolve_upload_file_name(file, file_name)
        ftype = (
            file_type.strip()
            if file_type and file_type.strip()
            else self._infer_feishu_file_type(name)
        )
        client = self._get_client()
        file_key = await self._upload_file_get_key(
            client,
            data,
            file_name=name,
            file_type=ftype,
            duration_ms=duration_ms,
        )
        content = json.dumps({"file_key": file_key}, ensure_ascii=False)
        body = (
            CreateMessageRequestBody.builder()
            .receive_id(receive_id)
            .msg_type("file")
            .content(content)
            .build()
        )
        req = (
            CreateMessageRequest.builder()
            .receive_id_type(receive_id_type)
            .request_body(body)
            .build()
        )
        resp = await client.im.v1.message.acreate(req)
        if not resp.success():
            logger.error(f"Feishu send file failed: code={resp.code}, msg={resp.msg}")
            raise RuntimeError(f"Feishu API error: {resp.msg}")
        msg_id = getattr(resp.data, "message_id", None) or "unknown"
        return f"File sent. message_id: {msg_id}"

    async def send_audio_message(
        self,
        audio: str,
        receive_id: Optional[str] = None,
        receive_id_type: str = "user_id",
        file_name: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> str:
        """Send a voice / audio message (async).

        Feishu only accepts **OPUS** for this flow: upload via ``im/v1/files`` with
        ``file_type=opus``, then send ``msg_type=audio``.

        ``audio`` may be a URL or a local path. The upload filename must end with
        ``.opus`` (set ``file_name`` when the URL has no sensible name). Other formats
        (e.g. mp3) must be converted first, e.g.::

            ffmpeg -i in.mp3 -acodec libopus -ac 1 -ar 16000 out.opus

        ``duration_ms`` is optional but recommended so clients can show duration (same as
        the file upload API). Max file size 30 MB.
        """
        if not audio or not str(audio).strip():
            raise ValueError("audio is required")
        if not receive_id:
            raise ValueError("receive_id is required")
        data = await self._load_bytes_from_source(audio)
        name = self._resolve_upload_file_name(audio, file_name)
        if Path(name).suffix.lower() != ".opus":
            raise ValueError(
                "Feishu voice requires an OPUS file: filename must end with .opus "
                "(set file_name for bare URLs). Convert with e.g. "
                "ffmpeg -i input.mp3 -acodec libopus -ac 1 -ar 16000 output.opus"
            )
        client = self._get_client()
        file_key = await self._upload_file_get_key(
            client,
            data,
            file_name=name,
            file_type="opus",
            duration_ms=duration_ms,
        )
        content = json.dumps({"file_key": file_key}, ensure_ascii=False)
        body = (
            CreateMessageRequestBody.builder()
            .receive_id(receive_id)
            .msg_type("audio")
            .content(content)
            .build()
        )
        req = (
            CreateMessageRequest.builder()
            .receive_id_type(receive_id_type)
            .request_body(body)
            .build()
        )
        resp = await client.im.v1.message.acreate(req)
        if not resp.success():
            logger.error(f"Feishu send audio failed: code={resp.code}, msg={resp.msg}")
            raise RuntimeError(f"Feishu API error: {resp.msg}")
        msg_id = getattr(resp.data, "message_id", None) or "unknown"
        return f"Audio sent. message_id: {msg_id}"

    async def send_video_message(
        self,
        video: str,
        receive_id: Optional[str] = None,
        receive_id_type: str = "user_id",
        file_name: Optional[str] = None,
        duration_ms: Optional[int] = None,
        thumbnail: Optional[str] = None,
    ) -> str:
        """Send a video message (async).

        Uses ``msg_type=media`` after uploading the video with ``file_type=mp4`` via
        ``im/v1/files``. Feishu expects **MP4** for this path; the upload filename must
        end with ``.mp4`` (set ``file_name`` for bare URLs).

        ``video`` may be a URL or a local path. ``duration_ms`` is optional but
        recommended for clients to show length. Max video size 30 MB (same as file API).

        ``thumbnail`` is optional: a URL or path to a cover image; if set, it is uploaded
        via ``im/v1/images`` and sent as ``image_key`` in the media payload.
        """
        if not video or not str(video).strip():
            raise ValueError("video is required")
        if not receive_id:
            raise ValueError("receive_id is required")
        data = await self._load_bytes_from_source(video)
        name = self._resolve_upload_file_name(video, file_name)
        if Path(name).suffix.lower() != ".mp4":
            raise ValueError(
                "Feishu video requires an MP4 file: filename must end with .mp4 "
                "(set file_name for bare URLs)."
            )
        client = self._get_client()
        file_key = await self._upload_file_get_key(
            client,
            data,
            file_name=name,
            file_type="mp4",
            duration_ms=duration_ms,
        )
        payload: Dict[str, str] = {"file_key": file_key}
        if thumbnail and str(thumbnail).strip():
            thumb_bytes = await self._load_bytes_from_source(thumbnail.strip())
            payload["image_key"] = await self._upload_image_get_key(client, thumb_bytes)
        content = json.dumps(payload, ensure_ascii=False)
        body = (
            CreateMessageRequestBody.builder()
            .receive_id(receive_id)
            .msg_type("media")
            .content(content)
            .build()
        )
        req = (
            CreateMessageRequest.builder()
            .receive_id_type(receive_id_type)
            .request_body(body)
            .build()
        )
        resp = await client.im.v1.message.acreate(req)
        if not resp.success():
            logger.error(f"Feishu send video failed: code={resp.code}, msg={resp.msg}")
            raise RuntimeError(f"Feishu API error: {resp.msg}")
        msg_id = getattr(resp.data, "message_id", None) or "unknown"
        return f"Video sent. message_id: {msg_id}"

