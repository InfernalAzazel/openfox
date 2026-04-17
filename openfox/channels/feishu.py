import asyncio
import contextlib
import io
import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union
from urllib.parse import unquote, urlparse

from agno.workflow import RemoteWorkflow, Workflow
import httpx
from agno.agent import Agent, RunOutput
from agno.run.base import RunStatus
from agno.utils.log import logger
import lark_oapi as lark
from lark_oapi.api.im.v1 import *
from lark_oapi.api.im.v1.model.p2_im_message_receive_v1 import P2ImMessageReceiveV1
from openfox.tools.config import ConfigTools
from agno.agent.remote import RemoteAgent
from agno.team.remote import RemoteTeam
from agno.team.team import Team
from .base import BaseChannel

class FeishuChannel(BaseChannel):
    def __init__(
        self,
        agent: Optional[Union[Agent, RemoteAgent]] = None,
        team: Optional[Union[Team, RemoteTeam]] = None,
        workflow: Optional[Union[Workflow, RemoteWorkflow]] = None,
    ):
        self.config_tools = ConfigTools()
        self.config = self.config_tools.load()
        self.type = "feishu"
        self.app_id = self.config.channels.feishu.app_id
        self.app_secret = self.config.channels.feishu.app_secret
        
        self.runner = agent or team or workflow

        # Feishu async API client
        self.client = (
            lark.Client.builder()
            .app_id(self.app_id)
            .app_secret(self.app_secret)
            .build()
        )
        self.event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(lambda data: asyncio.create_task(self._on_p2_im_message_receive_v1(data)))
            .build()
        )
        self.ws_client: Optional[lark.ws.Client] = None

    async def handle_event(
        self,
        req: lark.RawRequest,
        task_adder: Optional[Callable[[Callable[..., Any], Any], Any]] = None,
    ):
        """
        Handle Feishu HTTP callback requests with the same channel logic.
        """
        if task_adder:
            callback = lambda data: task_adder(self._on_p2_im_message_receive_v1, data)
        else:
            callback = lambda data: asyncio.create_task(self._on_p2_im_message_receive_v1(data))
        handler = (
            lark.EventDispatcherHandler.builder(self.encrypt_key, self.verification_token)
            .register_p2_im_message_receive_v1(callback)
            .build()
        )
        return handler.do(req)

    async def start(self):
        self.ws_client = lark.ws.Client(
            app_id=self.app_id,
            app_secret=self.app_secret,
            event_handler=self.event_handler,
            log_level=lark.LogLevel.INFO,
        )
        # SDK start is blocking; run it in a worker thread.
        await asyncio.to_thread(self.ws_client.start)

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

    async def _upload_image_get_key(self, image_bytes: bytes) -> str:
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

    async def send_message(
        self,
        receive_id: str,
        content: Any,
        msg_type: str = "text",
        receive_id_type: str = "user_id",
        use_markdown: bool = False,
        italics: bool = False,
        file_name: Optional[str] = None,
        file_type: Optional[str] = None,
        duration_ms: Optional[int] = None,
        thumbnail: Optional[str] = None,
        **kwargs
    ):
        """Unified async message sending interface."""
        if msg_type == "text":
            if isinstance(content, dict):
                payload = content
                real_type = msg_type
            else:
                text = str(content or "")
                if italics:
                    text = "\n".join(f"_{line}_" for line in text.split("\n"))
                if use_markdown:
                    payload = {
                        "schema": "2.0",
                        "body": {
                            "elements": [
                                {"tag": "markdown", "content": text},
                            ]
                        },
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

        if msg_type == "image":
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

        if msg_type == "file":
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

        if msg_type == "audio":
            if isinstance(content, dict):
                payload = content
            else:
                source = str(content)
                data = await self._load_bytes_from_source(source)
                name = self._resolve_upload_file_name(source, file_name)
                if Path(name).suffix.lower() != ".opus":
                    raise ValueError(
                        "Feishu voice requires an OPUS file: filename must end with .opus"
                    )
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

        if msg_type == "media":
            if isinstance(content, dict):
                payload = content
            else:
                source = str(content)
                data = await self._load_bytes_from_source(source)
                name = self._resolve_upload_file_name(source, file_name)
                if Path(name).suffix.lower() != ".mp4":
                    raise ValueError(
                        "Feishu video requires an MP4 file: filename must end with .mp4"
                    )
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

        raise ValueError(f"Unsupported msg_type: {msg_type}")

    async def _on_p2_im_message_receive_v1(self, data: P2ImMessageReceiveV1) -> None:
        """Unified incoming message handling flow (migrated from router)."""
        if self.runner is None:
            logger.warning("FeishuChannel.runner is not set, skip message handling.")
            return

        header = data.header
        ev = data.event
        if not ev or not ev.sender or not ev.message:
            return None

        message_id = ev.message.message_id
        event_id = header.event_id
        open_id = ev.sender.sender_id.open_id
        chat_id = ev.message.chat_id
        message_type = ev.message.message_type
        message = ""

        if message_type != "text":
            return

        with contextlib.suppress(json.JSONDecodeError, TypeError):
            message = json.loads(ev.message.content).get("text", "")

        logger.info(
            f"[Feishu] event_id={event_id} message_type={message_type} message_id={message_id}\n"
            + f"open_id={open_id} chat_id={chat_id}: {message[:80]}..."
        )

        try:
            # Inject channel metadata into model context for downstream scheduling.
            response = await self.runner.arun(
                message,
                user_id=open_id,
                session_id=f"channel:{open_id}",
                dependencies={"channel": {"type": "feishu", "open_id": open_id, "chat_id": chat_id}},
                add_dependencies_to_context=True,
            )
        except Exception as e:
            logger.error(f"Feishu message handling error: {e}")
            await self.send_message(
                receive_id=chat_id,
                content="Something went wrong while handling your message. Please try again later.",
                msg_type="text",
                receive_id_type="chat_id",
                use_markdown=True,
            )
            return

        if response.status == "ERROR":
            await self.send_message(
                receive_id=chat_id,
                content="An error occurred while processing your request. Please try again later.",
                msg_type="text",
                receive_id_type="chat_id",
                use_markdown=True,
            )
            logger.error(response.content)
            return

        if response.reasoning_content:
            await self.send_message(
                receive_id=chat_id,
                content=f"Reasoning:\n{response.reasoning_content}",
                msg_type="text",
                receive_id_type="chat_id",
                italics=True,
                use_markdown=True,
            )

        if response.images:
            for i in range(len(response.images)):
                await self.send_message(
                    receive_id=chat_id,
                    content=response.content or f"[Image {i + 1}]",
                    msg_type="text",
                    receive_id_type="chat_id",
                    use_markdown=True,
                )
        else:
            await self.send_message(
                receive_id=chat_id,
                content=response.content or "",
                msg_type="text",
                receive_id_type="chat_id",
                use_markdown=True,
            )

    async def on_notify_scheduled(
        self,
        run_output: RunOutput,
        channel: Dict[str, Any]
    ) -> None:
        """Send Feishu notifications after a scheduled Agno run."""
        ctype = channel.get("type")
        if ctype and ctype != self.type:
            return

        chat_id = channel.get("chat_id")
        receive_id = channel.get("receive_id") or (str(chat_id) if chat_id else None)
        receive_id_type = channel.get("receive_id_type") or ("chat_id" if chat_id else "user_id")

        if not receive_id:
            logger.warning("scheduled_notify: feishu channel missing receive_id/chat_id, skipping")
            return

        if run_output.status == RunStatus.error:
            body = run_output.content if isinstance(run_output.content, str) else str(run_output.content or "")
            text = body.strip() or "The scheduled task failed"
            await self.send_message(
                receive_id=receive_id,
                content=text,
                msg_type="text",
                receive_id_type=receive_id_type,
                use_markdown=True,
            )
            return

        if run_output.reasoning_content:
            await self.send_message(
                receive_id=receive_id,
                content=f"Reasoning:\n{run_output.reasoning_content}",
                msg_type="text",
                receive_id_type=receive_id_type,
                use_markdown=True,
                italics=True,
            )

        if run_output.images:
            for i in range(len(run_output.images)):
                await self.send_message(
                    receive_id=receive_id,
                    content=run_output.content or f"[Image {i + 1}]",
                    msg_type="text",
                    receive_id_type=receive_id_type,
                    use_markdown=True,
                )
        else:
            await self.send_message(
                receive_id=receive_id,
                content=run_output.content or "",
                msg_type="text",
                receive_id_type=receive_id_type,
                use_markdown=True,
            )