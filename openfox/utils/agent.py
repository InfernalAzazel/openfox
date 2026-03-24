from contextlib import asynccontextmanager
from agno.agent import Agent
from agno.models.litellm import LiteLLM
from agno.os import AgentOS
from agno.os.settings import AgnoAPISettings
from agno.skills import Skills, LocalSkills
from agno.scheduler import ScheduleManager
from openfox.interfaces.feishu import Feishu
from openfox.tools.scheduler import CronTools
from openfox.tools.shell import run_shell
from openfox.tools.akshare_stock import AkshareStockTools
from openfox.tools.feishu import FeishuTools
from openfox.tools.mcp_config import MCPConfigTools
from openfox.db.agno_mongo import AsyncMongoDb
from openfox.utils.schedule_notice import ScheduleNotice
from agno.tools import Toolkit
from typing import List, Optional
from agno.tools.mcp import MultiMCPTools
from mcp import StdioServerParameters
from agno.tools.mcp.params import StreamableHTTPClientParams
from openfox.tools.config import ConfigTools
from openfox.modes.config import Config


# Work around agno ScheduleManager: on interpreter exit, __del__ may run without `_pool` set.
ScheduleManager.close = lambda self: (getattr(self, "_pool", None) and (self._pool.shutdown(wait=False), setattr(self, "_pool", None)))


def make_lifespan(db, tools: List[Toolkit] = []):

    @asynccontextmanager
    async def _lifespan(app):
        sn = ScheduleNotice(db)
        for tool in tools:
            sn.add_handler(tool.on_change)
        await sn.start()
        yield
        await sn.stop()
        await db.close()

    return _lifespan

def build_mcps(config: Config) -> Optional[MultiMCPTools]:
    """Build MultiMCPTools from application config."""
    if not config.mcps:
        return None

    server_params = []
    timeout_seconds = 30

    for mcp_cfg in config.mcps:
        if mcp_cfg.command:
            server_params.append(
                StdioServerParameters(
                    command=mcp_cfg.command,
                    args=mcp_cfg.args,
                    env=mcp_cfg.env or None,
                )
            )
            timeout_seconds = max(timeout_seconds, mcp_cfg.tool_timeout)
        elif mcp_cfg.url:
            server_params.append(
                StreamableHTTPClientParams(
                    url=mcp_cfg.url,
                    headers=mcp_cfg.headers or None,
                )
            )
            timeout_seconds = max(timeout_seconds, mcp_cfg.tool_timeout)

    if not server_params:
        return None

    return MultiMCPTools(
        server_params_list=server_params,
        timeout_seconds=timeout_seconds,
        allow_partial_failure=True,
    )

class OpenFoxAgent:
    """Wires OpenFox config, storage, tools, and AgentOS runtime."""

    def __init__(self):
        self.feishu_tools = FeishuTools()
        self.config_tools = ConfigTools()
        self.mcp_config_tools = MCPConfigTools(self.config_tools)
        self.config = self.config_tools.load()
        self.db = AsyncMongoDb(db_url=self.config.db_url, db_name=self.config.db_name)
        self.schedule_mgr = ScheduleManager(self.db)

        self.instructions = [
            "当用户要求定时或周期执行任务时使用 CronTools.create。",
            "用户说「每X帮我做Y」时：将「每X」映射为 cron_expr（例如每分钟→* * * * *）。",
            "将「帮我做Y」整句作为 message：message 是到点时 Agent 要执行的任务正文（可含工具调用），不要包含时间或周期描述。",
            "从用户文本中自动提取创建定时任务所需的参数（cron_expr、message、channel、timezone）。",
            "当用户询问有哪些定时任务时使用 CronTools.list。",
            "若技能文档给出 CLI 示例，必须使用 run_shell 执行。",
            "当用户希望通过聊天配置 MCP 时，使用 mcp_config 工具。",
            f"默认时区为 {self.config.time_zone}。",
        ]

        mcps = build_mcps(self.config)

        tools_list: List[Toolkit] = [
            run_shell,
            CronTools(endpoint=f"/agents/{self.config.agent_id}/runs", schedule_mgr=self.schedule_mgr),
            AkshareStockTools(),
            self.feishu_tools,
            self.mcp_config_tools,
        ]
        if mcps is not None:
            tools_list.append(mcps)

        self.agent = Agent(
            id=self.config.agent_id,
            model=LiteLLM(
                id=self.config.llm.model_name,
                api_key=self.config.llm.api_key,
                api_base=self.config.llm.api_base,
            ),
            tools=tools_list,
            skills=Skills(loaders=[LocalSkills(self.config.skills_path)]),
            db=self.db,
            markdown=True,
        )
        settings = AgnoAPISettings(
            os_security_key=self.config.os_security_key,
            docs_enabled=self.config.docs_enabled,
            authorization_enabled=self.config.authorization_enabled,
            cors_origin_list=self.config.cors_origin_list if self.config.cors_origin_list else None,
        )

        self.os = AgentOS(
            name=self.config.agent_id,
            agents=[self.agent],
            interfaces=[Feishu(agent=self.agent)],
            db=self.db,
            scheduler=True,
            scheduler_poll_interval=15,
            lifespan=make_lifespan(self.db, [self.feishu_tools]),
            settings=settings,
        )
        self.app = self.os.get_app()