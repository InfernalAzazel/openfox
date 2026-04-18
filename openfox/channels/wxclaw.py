import asyncio
import signal
import sys
from typing import Any, Dict, Optional, Union
from agno.agent import Agent, RunOutput
from agno.agent.remote import RemoteAgent
from agno.run import RunStatus
from agno.team.remote import RemoteTeam
from agno.team.team import Team
from agno.utils.log import logger
from agno.workflow import RemoteWorkflow, Workflow
from openilink import Client, LoginCallbacks, MonitorOptions, TypingStatus, WeixinMessage, print_qrcode, extract_text
from openfox.tools.wxclaw import BUF_FILE, TOKEN_FILE, WxClawTools
from .base import BaseChannel



class WxClawChannel(BaseChannel):
    """WeChat channel implemented with openilink SDK primitives."""

    def __init__(
        self,
        agent: Optional[Union[Agent, RemoteAgent]] = None,
        team: Optional[Union[Team, RemoteTeam]] = None,
        workflow: Optional[Union[Workflow, RemoteWorkflow]] = None,
    ):
        self.type = "wxclaw"
        self.runner = agent or team or workflow
        self.wxclaw_tools = WxClawTools()
        self.client: Optional[Client] = None

    def _on_message(self, message: WeixinMessage) -> None:
        try:
            asyncio.run(self._on_message_async(message))
        except Exception as e:
            logger.error(f"WxClaw _on_message error: {e}")


    async def _on_message_async(self, message: WeixinMessage) -> None:
        text = extract_text(message)
        if not text:
            return
        from_user_id = message.from_user_id
        context_token = message.context_token
        logger.info(f"[WxClaw] from_user_id={from_user_id} context_token={context_token} message_id={message.message_id}: {text[:80]}")
        config = self.client.get_config(from_user_id, context_token)
        try:
            self.client.send_typing(from_user_id, config.typing_ticket)
            # Inject channel metadata into model context for downstream scheduling.
            response = await self.runner.arun(
                text,
                user_id=from_user_id,
                session_id=f"channel:{from_user_id}",
                dependencies={"channel": {"type": "wxclaw", "from_user_id": from_user_id, "context_token": context_token}},
                add_dependencies_to_context=True,
            )
        except Exception as e:
            logger.error(f"WxClaw message handling error: {e}")
            await asyncio.to_thread(
                self.wxclaw_tools.send_text,
                from_user_id,
                context_token,
                "Something went wrong while handling your message. Please try again later.",
            )
            self.client.send_typing(from_user_id, config.typing_ticket, TypingStatus.CANCEL)
            return

        if response.status == "ERROR":
            await asyncio.to_thread(
                self.wxclaw_tools.send_text,
                from_user_id,
                context_token,
                "An error occurred while processing your request. Please try again later.",
            )
            self.client.send_typing(from_user_id, config.typing_ticket, TypingStatus.CANCEL)
            logger.error(response.content)
            return

        if response.reasoning_content:
            await asyncio.to_thread(self.wxclaw_tools.send_text, from_user_id, context_token, f"Reasoning:\n{response.reasoning_content}", italics=True)
            self.client.send_typing(from_user_id, config.typing_ticket, TypingStatus.CANCEL)

        if response.images:
            for i in range(len(response.images)):
                await asyncio.to_thread(self.wxclaw_tools.send_text, from_user_id, context_token, f"[Image {i + 1}]")
                self.client.send_typing(from_user_id, config.typing_ticket, TypingStatus.CANCEL)
        else:
            await asyncio.to_thread(self.wxclaw_tools.send_text, from_user_id, context_token, response.content or "")
            self.client.send_typing(from_user_id, config.typing_ticket, TypingStatus.CANCEL)

    def start(self):
        token = self.wxclaw_tools.load_file(TOKEN_FILE)
        self.client = Client(token=token)
        if not token:
            result = self.client.login_with_qr(
                callbacks=LoginCallbacks(
                    on_qrcode=print_qrcode,
                    on_scanned=lambda: print("QR code scanned — please confirm on your phone."),
                )
            )
            if not result.connected:
                logger.error(f"WxClaw login failed: {result.message}")
                sys.exit(1)
            TOKEN_FILE.write_text(result.bot_token)
            logger.info(f"WxClaw login OK. bot_id={result.bot_id}")
            self.client = Client(token=result.bot_token)

        self.client.monitor(self._on_message, opts=MonitorOptions(
            initial_buf=self.wxclaw_tools.load_file(BUF_FILE),
            on_buf_update=lambda buf: BUF_FILE.write_text(buf),
            on_error=lambda e: logger.error(f"WxClaw monitor error: {e}"),
            on_session_expired=lambda: logger.error(
                "WxClaw session expired; scan QR again to log in."
            ),
        ))

    async def on_notify_scheduled(self, run_output: RunOutput, channel: Dict[str, Any]) -> None:
        ctype = channel.get("type")
        if ctype and ctype != self.type:
            return

        from_user_id = channel.get("from_user_id")
        context_token = channel.get("context_token")

        if not from_user_id:
            logger.warning("scheduled_notify: wxclaw channel missing from_user_id, skipping")
            return

        config = self.client.get_config(from_user_id, context_token)
        self.client.send_typing(from_user_id, config.typing_ticket)
        if run_output.status == RunStatus.error:
            body = run_output.content if isinstance(run_output.content, str) else str(run_output.content or "")
            text = body.strip() or "The scheduled task failed"
            await asyncio.to_thread(self.wxclaw_tools.push, text)
            self.client.send_typing(from_user_id, config.typing_ticket, TypingStatus.CANCEL)
            return

        if run_output.reasoning_content:
            await asyncio.to_thread(self.wxclaw_tools.push, f"Reasoning:\n{run_output.reasoning_content}", italics=True)
            self.client.send_typing(from_user_id, config.typing_ticket, TypingStatus.CANCEL)

        if run_output.images:
            for i in range(len(run_output.images)):
                await asyncio.to_thread(self.wxclaw_tools.push, f"[Image {i + 1}]")
                self.client.send_typing(from_user_id, config.typing_ticket, TypingStatus.CANCEL)
        else:
            await asyncio.to_thread(self.wxclaw_tools.push, run_output.content or "")
            self.client.send_typing(from_user_id, config.typing_ticket, TypingStatus.CANCEL)
