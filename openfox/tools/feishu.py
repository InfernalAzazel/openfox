import json
from typing import Any, Dict, List, Optional
from agno.tools import Toolkit
from agno.utils.log import logger
from agno.utils.log import log_info, log_warning
from openfox.tools.config import ConfigTools
from lark_oapi import Client


class FeishuTools(Toolkit):
    """飞书 API 工具：发送消息等。"""

    def __init__(self,):
        """初始化飞书工具"""
        self.config_tools = ConfigTools()
        self.config = self.config_tools.load_config()
        self.app_id = self.config.channels.feishu.app_id
        self.app_secret = self.config.channels.feishu.app_secret
        self.encrypt_key = self.config.channels.feishu.encrypt_key
        self.verification_token = self.config.channels.feishu.verification_token

        self.tools: List[Any] = [self.send_text_message]

        super().__init__(name="feishu", tools=self.tools)

    def _get_client(self):
        """获取 lark_oapi Client（带 app 凭证）。"""
        return Client.builder().app_id(self.app_id).app_secret(self.app_secret).build()

    def _build_content(self, text: str, use_markdown: bool = False) -> tuple[str, str]:
        """构造发送用 msg_type 与 content 字符串。

        use_markdown=True 时，使用飞书卡片 JSON v2 的富文本（Markdown）组件：
        https://open.feishu.cn/document/feishu-cards/card-json-v2-components/content-components/rich-text
        """
        if use_markdown:
            card: Dict[str, Any] = {
                "schema": "2.0",
                "body": {
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": text,
                        }
                    ]
                },
            }
            return "interactive", json.dumps(card, ensure_ascii=False)
        return "text", json.dumps({"text": text}, ensure_ascii=False)

    async def send_text_message(
        self,
        text: str = "",
        receive_id: Optional[str] = None,
        receive_id_type: str = 'user_id',
        use_markdown: bool = True,
        italics: bool = False,
        chunk_size: int = 4000,
    ) -> str:
        """向飞书用户或群聊发送消息（异步）。支持纯文本或 Markdown。

        - use_markdown=True 时按富文本 Markdown 组件渲染；
        - italics=True 时，对整段文本按行包一层斜体；
        - 超出 chunk_size 时自动分片多次发送。
        """

        if italics:
            text = "\n".join(f"_{line}_" for line in text.split("\n"))

        # 分片发送，返回最后一条消息的 message_id 描述
        last_msg_desc = ""
        for i in range(0, len(text), chunk_size):
            chunk = text[i : i + chunk_size]
            msg_type, content = self._build_content(chunk, use_markdown=use_markdown)
            logger.debug(f"飞书发送消息(异步,{msg_type}) -> {receive_id_type}:{receive_id}: {chunk[:50]}...")

            client = self._get_client()
            from lark_oapi.api.im.v1.model.create_message_request import CreateMessageRequest
            from lark_oapi.api.im.v1.model.create_message_request_body import CreateMessageRequestBody

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
                logger.error(f"飞书发送消息失败: code={resp.code}, msg={resp.msg}")
                raise RuntimeError(f"飞书 API 错误: {resp.msg}")

            msg_id = getattr(resp.data, "message_id", None) or "unknown"
            last_msg_desc = f"消息已发送。message_id: {msg_id}"

        return last_msg_desc or "未发送任何消息"

    async def on_change(self, schedule_doc: Dict[str, Any], run_doc: Dict[str, Any]) -> None:
        """定时任务执行结果回调：根据 schedule.channel 里配置的飞书通道发送通知。"""

        payload = schedule_doc.get("payload") or {}
        channel = payload.get("channel") or {}
        chat_id = channel.get("chat_id") or ""

        status = run_doc.get("status")
        run_id = run_doc.get("id") or run_doc.get("_id")
        schedule_id = run_doc.get("schedule_id")
        output_content = str((run_doc.get("output") or {}).get("content", ""))


        if channel.get("type") != "feishu" or not chat_id:
            return

        if status == "success":
            await self.send_text_message(
                text=str(output_content) or "任务执行成功，但无输出内容。",
                receive_id=chat_id,
                receive_id_type="chat_id",
                use_markdown=True,
            )
            log_info(
                "ScheduleNotice 捕获到成功调度: "
                + f"schedule_id={schedule_id}, run_id={run_id}"
            )
        elif status == "failed":
            error = run_doc.get("error")
            await self.send_text_message(
                text=f"定时任务执行失败：{error}",
                receive_id=chat_id,
                receive_id_type="chat_id",
                use_markdown=True,
            )
            log_warning(
                "ScheduleNotice 捕获到失败调度: "
                + f"schedule_id={schedule_id}, run_id={run_id}, error={error}"
            )
