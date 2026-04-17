import asyncio
import contextlib
import json
from typing import Any, Dict, Optional, Union

from agno.workflow import RemoteWorkflow, Workflow
from agno.agent import Agent, RunOutput
from agno.run.base import RunStatus
from agno.utils.log import logger
import lark_oapi as lark
from lark_oapi.api.im.v1.model.p2_im_message_receive_v1 import P2ImMessageReceiveV1
from openfox.tools.feishu import FeiShuTools
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
        self.type = "feishu"
        self.feishu_tools = FeiShuTools()
        self.app_id = self.feishu_tools.app_id
        self.app_secret = self.feishu_tools.app_secret
        self.runner = agent or team or workflow
    
        self.event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(lambda data: asyncio.create_task(self._on_p2_im_message_receive_v1(data)))
            .build()
        )
        self.ws_client: Optional[lark.ws.Client] = None


    async def start(self):
        self.ws_client = lark.ws.Client(
            app_id=self.app_id,
            app_secret=self.app_secret,
            event_handler=self.event_handler,
            log_level=lark.LogLevel.INFO,
        )
        # SDK start is blocking; run it in a worker thread.
        await asyncio.to_thread(self.ws_client.start)

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
            await self.feishu_tools.send_text_message(
                receive_id=chat_id,
                content="Something went wrong while handling your message. Please try again later.",
                receive_id_type="chat_id",
                use_markdown=True,
            )
            return

        if response.status == "ERROR":
            await self.feishu_tools.send_text_message(
                receive_id=chat_id,
                content="An error occurred while processing your request. Please try again later.",
                receive_id_type="chat_id",
                use_markdown=True,
            )
            logger.error(response.content)
            return

        if response.reasoning_content:
            await self.feishu_tools.send_text_message(
                receive_id=chat_id,
                content=f"Reasoning:\n{response.reasoning_content}",
                receive_id_type="chat_id",
                italics=True,
                use_markdown=True,
            )

        if response.images:
            for i in range(len(response.images)):
                await self.feishu_tools.send_text_message(
                    receive_id=chat_id,
                    content=response.content or f"[Image {i + 1}]",
                    receive_id_type="chat_id",
                    use_markdown=True,
                )
        else:
            await self.feishu_tools.send_text_message(
                receive_id=chat_id,
                content=response.content or "",
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
            await self.feishu_tools.send_text_message(
                receive_id=receive_id,
                content=text,
                receive_id_type=receive_id_type,
                use_markdown=True,
            )
            return

        if run_output.reasoning_content:
            await self.feishu_tools.send_text_message(
                receive_id=receive_id,
                content=f"Reasoning:\n{run_output.reasoning_content}",
                receive_id_type=receive_id_type,
                use_markdown=True,
                italics=True,
            )

        if run_output.images:
            for i in range(len(run_output.images)):
                await self.feishu_tools.send_text_message(
                    receive_id=receive_id,
                    content=run_output.content or f"[Image {i + 1}]",
                    receive_id_type=receive_id_type,
                    use_markdown=True,
                )
        else:
            await self.feishu_tools.send_text_message(
                receive_id=receive_id,
                content=run_output.content or "",
                receive_id_type=receive_id_type,
                use_markdown=True,
            )