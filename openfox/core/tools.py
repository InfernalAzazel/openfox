"""Default OpenFox agent toolkits (wired in ``OpenFoxAgent``)."""

from __future__ import annotations

from typing import List

from agno.scheduler import ScheduleManager
from agno.tools import Toolkit
from agno.tools.arxiv import ArxivTools
from agno.tools.calculator import CalculatorTools
from agno.tools.crawl4ai import Crawl4aiTools
from agno.tools.docker import DockerTools
from agno.tools.hackernews import HackerNewsTools
from agno.tools.pubmed import PubmedTools
from agno.tools.shell import ShellTools
from agno.tools.webbrowser import WebBrowserTools
from agno.tools.websearch import WebSearchTools
from agno.tools.wikipedia import WikipediaTools
from agno.tools.youtube import YouTubeTools

from openfox.schemas.config import Config
from openfox.tools.browser import BrowserTools
from openfox.tools.feishu import FeishuTools
from openfox.tools.mcp_config import MCPConfigTools
from openfox.tools.scheduler import CronTools
from openfox.utils.mcps import build_mcps


def build_openfox_toolkits(
    config: Config,
    schedule_mgr: ScheduleManager,
    feishu_tools: FeishuTools,
    mcp_config_tools: MCPConfigTools,
) -> List[Toolkit]:
    """Assemble the default toolkit list for the main agent."""
    mcps = build_mcps(config)
    tools_list: List[Toolkit] = [
        ShellTools(),
        CronTools(
            endpoint=f"/agents/{config.agent_id}/runs",
            schedule_mgr=schedule_mgr,
        ),
        BrowserTools(),
        feishu_tools,
        mcp_config_tools,
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
    return tools_list
