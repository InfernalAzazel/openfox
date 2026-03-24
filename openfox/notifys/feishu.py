from typing import Any, Dict
from agno.agent import RunOutput
from agno.run.base import RunStatus
from agno.utils.log import logger
from openfox.tools.feishu import FeishuTools


async def on_notify_scheduled(run_output: RunOutput, channel: Dict[str, Any]) -> None:
    """Registered as scheduled_notifier for type=feishu; uses chat_id from cron payload."""
    chat_id = channel.get("chat_id")
    if not chat_id:
        logger.warning("scheduled_notify: feishu channel missing chat_id, skipping")
        return

    tools = FeishuTools()
    receive_id = str(chat_id)
    receive_id_type = "chat_id"

    if run_output.status == RunStatus.error:
        body = run_output.content if isinstance(run_output.content, str) else str(run_output.content or "")
        text = body.strip() or "The scheduled task failed"
        await tools.send_text_message(text, receive_id=receive_id, receive_id_type=receive_id_type)
        return

    if run_output.reasoning_content:
        await tools.send_text_message(
            f"Reasoning:\n{run_output.reasoning_content}",
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            italics=True,
        )

    if run_output.images:
        for i in range(len(run_output.images)):
            await tools.send_text_message(
                run_output.content or f"[Image {i + 1}]",
                receive_id=receive_id,
                receive_id_type=receive_id_type,
            )
    else:
        await tools.send_text_message(
            run_output.content or "",
            receive_id=receive_id,
            receive_id_type=receive_id_type,
        )


register = ("feishu", on_notify_scheduled)