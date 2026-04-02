from pathlib import Path
from typing import List

from agno.agent import Agent
from agno.db.sqlite import AsyncSqliteDb
from agno.models.litellm import LiteLLM
from agno.os import AgentOS
from agno.os.settings import AgnoAPISettings
from agno.scheduler import ScheduleManager
from agno.skills import Skills, LocalSkills
from agno.tools import Toolkit
from openfox.interfaces.feishu import Feishu
from openfox.tools.config import ConfigTools
from openfox.tools.feishu import FeishuTools
from openfox.tools.mcp_config import MCPConfigTools
from openfox.tools.scheduler import CronTools
from openfox.tools.shell import run_shell
from openfox.utils.mcps import build_mcps
from openfox.utils.notify import send_notification
from openfox.tools.browser import BrowserTools
from openfox.routers import config
from openfox.routers import skills
from openfox.utils.web_static import install_web_routes
from agno.tools.websearch import WebSearchTools
from agno.tools.arxiv import ArxivTools
from agno.tools.hackernews import HackerNewsTools
from agno.tools.pubmed import PubmedTools
from agno.tools.wikipedia import WikipediaTools
from agno.tools.crawl4ai import Crawl4aiTools
from agno.tools.calculator import CalculatorTools
from agno.tools.docker import DockerTools
from agno.tools.shell import ShellTools
from agno.tools.youtube import YouTubeTools
from agno.tools.webbrowser import WebBrowserTools

# Work around agno ScheduleManager: on interpreter exit, __del__ may run without `_pool` set.
ScheduleManager.close = lambda self: (getattr(self, "_pool", None) and (self._pool.shutdown(wait=False), setattr(self, "_pool", None)))


class OpenFoxAgent:
    """Wires OpenFox config, storage, tools, and AgentOS runtime."""

    db_path = Path.home() / ".openfox" / "storage.db"

    def __init__(self):
        self.feishu_tools = FeishuTools()
        self.config_tools = ConfigTools()
        self.mcp_config_tools = MCPConfigTools(self.config_tools)
        self.config = self.config_tools.load()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = AsyncSqliteDb(db_file=str(self.db_path))
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
            ShellTools(),
            CronTools(
                endpoint=f"/agents/{self.config.agent_id}/runs",
                schedule_mgr=self.schedule_mgr,
            ),
            BrowserTools(),
            self.feishu_tools,
            self.mcp_config_tools,
            WebSearchTools(),
            ArxivTools(),
            HackerNewsTools(),
            PubmedTools(),
            WikipediaTools(),
            Crawl4aiTools(),
            CalculatorTools(),
            DockerTools(),
            YouTubeTools(),
            WebBrowserTools(),
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
            post_hooks=[send_notification],
        )
        
        settings = AgnoAPISettings(
            os_security_key=self.config.os_security_key,
            docs_enabled=self.config.docs_enabled,
            cors_origin_list=self.config.cors_origin_list,
        )

        self.os = AgentOS(
            name=self.config.agent_id,
            agents=[self.agent],
            interfaces=[Feishu(agent=self.agent)],
            db=self.db,
            scheduler=True,
            scheduler_poll_interval=15,
            settings=settings,
        )
        self.app = self.os.get_app()
        self.app.include_router(config.get_router(self.config_tools, settings))
        self.app.include_router(skills.get_router(self.config_tools, settings))
        install_web_routes(self.app)