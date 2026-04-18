import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from agno.utils.log import logger


@asynccontextmanager
async def app_lifespan(app: Any) -> AsyncIterator[None]:
    """
    OpenFox FastAPI lifespan hooks.

    Starts/stops configured channels with app lifecycle.
    """
    feishu_task: asyncio.Task[Any] | None = None
    wxclaw_task: asyncio.Task[Any] | None = None

    from openfox.channels.feishu import FeishuChannel
    from openfox.channels.wxclaw import WxClawChannel

    openfox_agent = app.state.openfox_agent
    config = openfox_agent.config

    if config.channels.feishu.activate:
        feishu_channel = FeishuChannel(agent=openfox_agent.agent)
        app.state.feishu_channel = feishu_channel
        logger.info("Starting Feishu websocket channel...")
        feishu_task = asyncio.create_task(feishu_channel.start())
        app.state.feishu_ws_task = feishu_task

    if config.channels.wxclaw.activate:
        wxclaw_channel = WxClawChannel(agent=openfox_agent.agent)
        app.state.wxclaw_channel = wxclaw_channel
        logger.info("Starting WxClaw channel...")
        # WxClaw monitor loop is synchronous and blocking; run it in a worker thread.
        wxclaw_task = asyncio.create_task(asyncio.to_thread(wxclaw_channel.start))
        app.state.wxclaw_task = wxclaw_task

    yield

    wx_channel = getattr(app.state, "wxclaw_channel", None)
    if wx_channel and getattr(wx_channel, "client", None):
        with contextlib.suppress(Exception):
            wx_channel.client.stop()

    for task in (feishu_task, wxclaw_task):
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task