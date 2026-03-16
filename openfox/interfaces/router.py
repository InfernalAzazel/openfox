import json
from typing import Optional, Union

import lark_oapi as lark
from json_repair import loads as json_repair_loads
from fastapi import APIRouter, Request, BackgroundTasks
from lark_oapi.api.im.v1.model.p2_im_message_receive_v1 import P2ImMessageReceiveV1
from agno.agent.agent import Agent
from agno.agent.remote import RemoteAgent
from agno.team.remote import RemoteTeam
from agno.team.team import Team
from agno.utils.log import log_error, log_info, log_warning
from agno.workflow import RemoteWorkflow, Workflow

from openfox.interfaces.security import (
    feishu_raw_request,
    feishu_raw_response,
    get_feishu_encrypt_key,
    get_feishu_verification_token,
)
from openfox.tools.feishu import FeishuTools


def _extract_message_text(message_type: str, content_str: str) -> str:
    """从事件内容解析出用户输入文本。"""
    if message_type != "text":
        return "当前仅支持文字消息，其它类型稍后支持。"
    if not content_str:
        return ""
    try:
        return (json_repair_loads(content_str).get("text") or "").strip()
    except Exception:
        return content_str.strip()

def attach_routes(
    router: APIRouter,
    agent: Optional[Union[Agent, RemoteAgent]] = None,
    team: Optional[Union[Team, RemoteTeam]] = None,
    workflow: Optional[Union[Workflow, RemoteWorkflow]] = None,
) -> APIRouter:
    if not (agent or team or workflow):
        raise ValueError("Either agent, team, or workflow must be provided.")

    runner = agent or team or workflow
    encrypt_key = get_feishu_encrypt_key()
    verification_token = get_feishu_verification_token()
    feishu_tools = FeishuTools()

    # 消息去重：飞书会从多节点推送同一事件，需用 message_id 去重（见 接收消息事件 https://open.larksuite.com/document/server-docs/im-v1/message/events/receive）
    _seen_message_ids: set[str] = set()
    _seen_max = 10_000

    @router.post("/webhook")
    async def webhook(request: Request, background_tasks: BackgroundTasks):
        """飞书事件回调：快速返回 200，具体处理放到 FastAPI BackgroundTasks 中执行。"""
        raw = await feishu_raw_request(request)

        def on_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
            """事件回调：只做去重和入队，真正处理在后台任务中完成。"""
            header = data.header
            ev = data.event
            if not ev or not ev.sender or not ev.message:
                return

            message_id = ev.message.message_id or ""
            if message_id:
                if message_id in _seen_message_ids:
                    return
                _seen_message_ids.add(message_id)
                if len(_seen_message_ids) > _seen_max:
                    _seen_message_ids.clear()

            event_id = header.event_id
            open_id = (ev.sender.sender_id and ev.sender.sender_id.open_id) or ""
            chat_id = ev.message.chat_id or ""
            message_type = ev.message.message_type or "text"
            content_str = ev.message.content or ""

            background_tasks.add_task(
                _process_message,
                feishu_tools,
                event_id,
                message_id,
                open_id,
                chat_id,
                message_type,
                content_str,
            )

        handler = (
            lark.EventDispatcherHandler.builder(encrypt_key, verification_token)
            .register_p2_im_message_receive_v1(on_p2_im_message_receive_v1)
            .build()
        )
        return feishu_raw_response(handler.do(raw))

    async def _process_message(feishu_tools: FeishuTools, event_id: str, message_id: str, open_id: str, chat_id: str, message_type: str, content_str: str) -> None:
        """处理一条飞书消息：解析输入、调用 runner，并发送所有回复。"""
        message_text = _extract_message_text(message_type, content_str)
        if not message_text:
            return

        log_info(
            f"[飞书消息] event_id={event_id} message_type={message_type} message_id={message_id}\n"
            + f"open_id={open_id} chat_id={chat_id}: {message_text[:80]}..."
        )
        channel={"channel": {"type": "feishu", "open_id": open_id, "chat_id": chat_id}}
        message_text = f"channel: {json.dumps(channel['channel'])}\n{message_text}"
        try:
            response = await runner.arun(message_text, user_id=open_id, session_id=f"feishu:{open_id}")
        except Exception as e:
            log_error(f"处理飞书消息异常: {e}")
            await feishu_tools.send_text_message("处理您的消息时出错，请稍后再试。", receive_id=chat_id, receive_id_type="chat_id")
            return

        if response.status == "ERROR":
            await feishu_tools.send_text_message("处理时发生错误，请稍后再试。", receive_id=chat_id, receive_id_type="chat_id")
            log_error(response.content)
            return

        if response.reasoning_content:
            await feishu_tools.send_text_message(f"思考过程：\n{response.reasoning_content}", receive_id=chat_id, receive_id_type="chat_id", italics=True)

        if response.images:
            for i in range(len(response.images)):
                await feishu_tools.send_text_message(response.content or f"[图片 {i + 1}]", receive_id=chat_id, receive_id_type="chat_id")
        else:
            await feishu_tools.send_text_message(response.content or "", receive_id=chat_id, receive_id_type="chat_id")

    return router
