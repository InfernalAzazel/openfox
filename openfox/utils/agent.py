from contextlib import asynccontextmanager
from agno.agent import Agent
from agno.models.litellm import LiteLLM
from agno.os import AgentOS
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


# 避免 agno 的 ScheduleManager 在解释器退出时因缺少 `_pool` 属性报错
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

    return _lifespan

def build_mcps(config: Config) -> Optional[MultiMCPTools]:
    """根据配置构建 MCP 工具集合。"""
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

class OpenMeshAgent:
    """封装 OpenMesh Agent 的配置、存储与运行时。"""

    AGENT_ID = "openfox"
    DEFAULT_TZ = "Asia/Shanghai"
    SKILLS_PATH = "openfox/skills"



    def __init__(self):
        self.feishu_tools = FeishuTools()
        self.config_tools = ConfigTools()
        self.mcp_config_tools = MCPConfigTools(self.config_tools)
        self.config = self.config_tools.load_config()
        self.db = AsyncMongoDb(db_url=self.config.db_url)
        self.schedule_mgr = ScheduleManager(self.db)

        self.instructions = [
            "当用户要求定时或周期执行任务时使用 CronTools.create",
            "用户说「每X帮我做Y」时：把「每X」转成 cron_expr（如每分钟→* * * * *），"
            "把「帮我做Y」整句作为 message；message 是到点时发给 Agent 的指令，不要包含时间词。",
            "当用户询问有哪些定时任务时使用 CronTools.list",
            "如果技能文档给出 CLI 示例，必须使用 run_shell 执行。",
            "当用户希望通过聊天配置 MCP 时，使用 mcp_config 工具。",
            f"默认 timezone 使用 {self.DEFAULT_TZ}。",
        ]

        mcps = build_mcps(self.config)

        tools_list: List[Toolkit] = [
            run_shell,
            CronTools(endpoint=f"/agents/{self.AGENT_ID}/runs", schedule_mgr=self.schedule_mgr),
            AkshareStockTools(),
            self.mcp_config_tools,
        ]
        if mcps is not None:
            tools_list.append(mcps)

        self.agent = Agent(
            id=self.AGENT_ID,
            model=LiteLLM(
                id=self.config.llm.model_name,
                api_key=self.config.llm.api_key,
                api_base=self.config.llm.api_base,
            ),
            tools=tools_list,
            skills=Skills(loaders=[LocalSkills("openfox/skills")]),
            db=self.db,
            markdown=True,
        )

        self.app = AgentOS(
            name="OpenMesh",
            agents=[self.agent],
            interfaces=[Feishu(agent=self.agent)],
            db=self.db,
            scheduler=True,
            scheduler_poll_interval=15,
            lifespan=make_lifespan(self.db, [self.feishu_tools]),
        ).get_app()


