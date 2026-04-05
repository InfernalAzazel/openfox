import contextlib
import json
from typing import Optional, Union
from httpx import Response
import lark_oapi as lark
from fastapi import APIRouter, Request, BackgroundTasks
from lark_oapi.api.im.v1.model.p2_im_message_receive_v1 import P2ImMessageReceiveV1
from agno.agent.agent import Agent
from agno.agent.remote import RemoteAgent
from agno.team.remote import RemoteTeam
from agno.team.team import Team
from agno.utils.log import logger
from agno.workflow import RemoteWorkflow, Workflow
from openfox.tools.feishu import FeishuTools


def attach_routes(
    router: APIRouter,
    agent: Optional[Union[Agent, RemoteAgent]] = None,
    team: Optional[Union[Team, RemoteTeam]] = None,
    workflow: Optional[Union[Workflow, RemoteWorkflow]] = None,
) -> APIRouter:
    if not (agent or team or workflow):
        raise ValueError("Either agent, team, or workflow must be provided.")

    runner = agent or team or workflow
    feishu_tools = FeishuTools()
    encrypt_key = feishu_tools.encrypt_key
    verification_token = feishu_tools.verification_token


    @router.post("/event")
    async def event(request: Request, background_tasks: BackgroundTasks):
        """Feishu event callback: return 200 immediately; handle the message in FastAPI BackgroundTasks."""
        req = lark.RawRequest()
        req.uri = request.url.path
        req.body = await request.body()
        req.headers = request.headers
    
        handler = (
            lark.EventDispatcherHandler.builder(encrypt_key, verification_token)
                .register_p2_im_message_receive_v1(
                    lambda data: background_tasks.add_task(_on_p2_im_message_receive_v1, data)
                )
                .build()
            )
            
        raw = handler.do(req)
        return Response(
            content=raw.content,
            status_code=raw.status_code or 200,
            headers=dict(raw.headers),
        )

    async def _on_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
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
            # dependencies write the channel to the model context, so that the payload of create_schedule can include the channel; when the schedule is triggered, the channel is passed to arun via the POST body.
            response = await runner.arun(
                message,
                user_id=open_id,
                session_id=f"channel:{open_id}",
                dependencies={"channel": {"type": "feishu", "open_id": open_id, "chat_id": chat_id}},
                add_dependencies_to_context=True,
            )
        except Exception as e:
            logger.error(f"Feishu message handling error: {e}")
            await feishu_tools.send_text_message(
                "Something went wrong while handling your message. Please try again later.",
                receive_id=chat_id,
                receive_id_type="chat_id",
            )
            return

        if response.status == "ERROR":
            await feishu_tools.send_text_message(
                "An error occurred while processing your request. Please try again later.",
                receive_id=chat_id,
                receive_id_type="chat_id",
            )
            logger.error(response.content)
            return

        if response.reasoning_content:
            await feishu_tools.send_text_message(
                f"Reasoning:\n{response.reasoning_content}",
                receive_id=chat_id,
                receive_id_type="chat_id",
                italics=True,
            )

        if response.images:
            for i in range(len(response.images)):
                await feishu_tools.send_text_message(
                    response.content or f"[Image {i + 1}]",
                    receive_id=chat_id,
                    receive_id_type="chat_id",
                )
        else:
            await feishu_tools.send_text_message(response.content or "", receive_id=chat_id, receive_id_type="chat_id")

    return router
