import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from agno.utils.log import logger


@asynccontextmanager
async def app_lifespan(app: Any) -> AsyncIterator[None]:
    """
    OpenFox FastAPI lifespan hooks.

    Starts/stops the Feishu websocket channel with app lifecycle.
    """
    ws_task: asyncio.Task[Any] | None = None

    from openfox.channels.feishu import FeishuChannel

    openfox_agent = app.state.openfox_agent
    channel = FeishuChannel(agent=openfox_agent.agent)
    app.state.feishu_channel = channel
    logger.info("Starting Feishu websocket channel...")
    ws_task = asyncio.create_task(channel.start())
    app.state.feishu_ws_task = ws_task

    yield

    if ws_task and not ws_task.done():
        ws_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await ws_task