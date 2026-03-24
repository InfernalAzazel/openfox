import json
from typing import Any, Dict, List, Optional

from agno.agent import RunOutput
from agno.run.base import RunStatus
from agno.tools import Toolkit
from agno.utils.log import logger
from lark_oapi import Client
from lark_oapi.api.im.v1.model.create_message_request import CreateMessageRequest
from lark_oapi.api.im.v1.model.create_message_request_body import CreateMessageRequestBody
from openfox.tools.config import ConfigTools


class FeishuTools(Toolkit):
    """Feishu (Lark) API toolkit: messaging helpers."""

    def __init__(self,):
        """Initialize Feishu tools from config."""
        self.config_tools = ConfigTools()
        self.config = self.config_tools.load()
        self.app_id = self.config.channels.feishu.app_id
        self.app_secret = self.config.channels.feishu.app_secret
        self.encrypt_key = self.config.channels.feishu.encrypt_key
        self.verification_token = self.config.channels.feishu.verification_token

        self.tools: List[Any] = [self.send_text_message]

        super().__init__(name="feishu", tools=self.tools)

    def _get_client(self) -> Client:
        return Client.builder().app_id(self.app_id).app_secret(self.app_secret).build()

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