"""Default OpenFox agent toolkits (wired in ``OpenFoxAgent``)."""

from __future__ import annotations

from pathlib import Path
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
from agno.tools.scheduler import SchedulerTools

from openfox.schemas.config import toolkit_filter_kwargs
from openfox.tools.config import ConfigTools
from openfox.tools.feishu import FeishuTools
from openfox.tools.mcp_config import MCPConfigTools
from openfox.utils.mcps import build_mcps

# Work around agno ScheduleManager: on interpreter exit, __del__ may run without `_pool` set.
ScheduleManager.close = lambda self: (getattr(self, "_pool", None) and (self._pool.shutdown(wait=False), setattr(self, "_pool", None)))

def build_openfox_toolkits(
    db,
    config_tools: ConfigTools,
    feishu_tools: FeishuTools,
) -> List[Toolkit]:
    """Assemble toolkits from ``config.tools`` (options follow Agno toolkit constructors)."""
    config = config_tools.load()
    tc = config.tools
    tools_list: List[Toolkit] = []

    tools_list.append(feishu_tools)

    if tc.scheduler.activate:
        tools_list.append(
            SchedulerTools(
                db=db,
                default_endpoint=f"/agents/{config.agent_id}/runs",
                default_timezone=config.time_zone,
                **toolkit_filter_kwargs(tc.scheduler),
            ),
        )

    if tc.mcp.activate:
         tools_list.append(MCPConfigTools(**toolkit_filter_kwargs(tc.mcp)))

    if tc.shell.activate:
        shell_kw: dict = {
            "enable_run_shell_command": tc.shell.enable_run_shell_command,
            "all": tc.shell.all,
        }
        if tc.shell.base_dir:
            shell_kw["base_dir"] = tc.shell.base_dir
        tools_list.append(ShellTools(**shell_kw, **toolkit_filter_kwargs(tc.shell)))

    if tc.websearch.activate:
        tools_list.append(
            WebSearchTools(
                enable_search=tc.websearch.enable_search,
                enable_news=tc.websearch.enable_news,
                backend=tc.websearch.backend,
                modifier=tc.websearch.modifier,
                fixed_max_results=tc.websearch.fixed_max_results,
                proxy=tc.websearch.proxy,
                timeout=tc.websearch.timeout,
                verify_ssl=tc.websearch.verify_ssl,
                timelimit=tc.websearch.timelimit,
                region=tc.websearch.region,
                **toolkit_filter_kwargs(tc.websearch),
            ),
        )

    if tc.arxiv.activate:
        arxiv_kw: dict = {
            "enable_search_arxiv": tc.arxiv.enable_search_arxiv,
            "enable_read_arxiv_papers": tc.arxiv.enable_read_arxiv_papers,
        }
        if tc.arxiv.download_dir:
            arxiv_kw["download_dir"] = Path(tc.arxiv.download_dir)
        tools_list.append(ArxivTools(**arxiv_kw, **toolkit_filter_kwargs(tc.arxiv)))

    if tc.hackernews.activate:
        tools_list.append(
            HackerNewsTools(
                enable_get_top_stories=tc.hackernews.enable_get_top_stories,
                enable_get_user_details=tc.hackernews.enable_get_user_details,
                all=tc.hackernews.all,
                **toolkit_filter_kwargs(tc.hackernews),
            ),
        )

    if tc.pubmed.activate:
        tools_list.append(
            PubmedTools(
                email=tc.pubmed.email,
                max_results=tc.pubmed.max_results,
                enable_search_pubmed=tc.pubmed.enable_search_pubmed,
                all=tc.pubmed.all,
                **toolkit_filter_kwargs(tc.pubmed),
            ),
        )

    if tc.wikipedia.activate:
        tools_list.append(WikipediaTools(**toolkit_filter_kwargs(tc.wikipedia)))

    if tc.crawl4ai.activate:
        tools_list.append(
            Crawl4aiTools(
                max_length=tc.crawl4ai.max_length,
                timeout=tc.crawl4ai.timeout,
                use_pruning=tc.crawl4ai.use_pruning,
                pruning_threshold=tc.crawl4ai.pruning_threshold,
                bm25_threshold=tc.crawl4ai.bm25_threshold,
                headless=tc.crawl4ai.headless,
                wait_until=tc.crawl4ai.wait_until,
                enable_crawl=tc.crawl4ai.enable_crawl,
                all=tc.crawl4ai.all,
                **toolkit_filter_kwargs(tc.crawl4ai),
            ),
        )

    if tc.calculator.activate:
        tools_list.append(CalculatorTools(**toolkit_filter_kwargs(tc.calculator)))

    if tc.docker.activate:
        tools_list.append(DockerTools(**toolkit_filter_kwargs(tc.docker)))

    if tc.youtube.activate:
        yt = tc.youtube
        tools_list.append(
            YouTubeTools(
                enable_get_video_captions=yt.all
                or (yt.get_video_captions and yt.enable_get_video_captions),
                enable_get_video_data=yt.all or (yt.get_video_data and yt.enable_get_video_data),
                enable_get_video_timestamps=yt.all or yt.enable_get_video_timestamps,
                all=yt.all,
                languages=yt.languages,
                **toolkit_filter_kwargs(yt),
            ),
        )

    if tc.webbrowser.activate:
        tools_list.append(
            WebBrowserTools(
                enable_open_page=tc.webbrowser.enable_open_page,
                all=tc.webbrowser.all,
                **toolkit_filter_kwargs(tc.webbrowser),
            ),
        )

    mcps = build_mcps(config)
    if mcps is not None:
        tools_list.append(mcps)

    return tools_list
