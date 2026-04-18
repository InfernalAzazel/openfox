from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from agno.vectordb.distance import Distance
from agno.vectordb.search import SearchType

# Agno toolkit index: https://docs.agno.com/tools/toolkits/overview

# Origins for the bundled ``/web`` UI on the default ``openfox serve`` port (CORS preflight).
OPENFOX_EMBEDDED_WEB_CORS_ORIGINS: tuple[str, ...] = (
    "http://127.0.0.1:7777",
    "http://localhost:7777",
)


class ToolkitFilterFields(BaseModel):
    """Optional Agno ``Toolkit`` tool-name filters (`selecting tools <https://docs.agno.com/tools/selecting-tools>`_)."""

    include_tools: Optional[List[str]] = Field(
        default=None,
        description="Only register these tool names (``Toolkit.include_tools``).",
    )
    exclude_tools: Optional[List[str]] = Field(
        default=None,
        description="Do not register these tool names (``Toolkit.exclude_tools``).",
    )


def toolkit_filter_kwargs(cfg: ToolkitFilterFields) -> dict[str, list[str]]:
    """Build ``include_tools`` / ``exclude_tools`` for Agno ``Toolkit`` subclasses."""
    out: dict[str, list[str]] = {}
    if cfg.include_tools is not None:
        out["include_tools"] = cfg.include_tools
    if cfg.exclude_tools is not None:
        out["exclude_tools"] = cfg.exclude_tools
    return out


class FeishuConfig(ToolkitFilterFields):
    """Feishu (Lark) channel settings."""

    activate: bool = Field(default=True, description="Register Feishu channel")
    app_id: str = Field(default="", description="Feishu Open Platform app ID")
    app_secret: str = Field(default="", description="Feishu Open Platform app secret")


class WxClawConfig(ToolkitFilterFields):
    """WeChat Claw channel settings."""

    activate: bool = Field(default=False, description="Register WeChat Claw channel")

class LLMConfig(BaseModel):
    """LLM settings."""

    model_name: str = Field(default="deepseek/deepseek-chat", description="Model name")
    api_base: str = Field(default="https://api.deepseek.com", description="API base URL")
    api_key: str = Field(default="", description="API key")


class EmbedderConfig(BaseModel):
    """LiteLLM embedding (``knowledge.vector_db.embedder``)."""

    id: str = Field(
        default="openai/text-embedding-v4",
        description="LiteLLM embedding model id; empty api_key/api_base inherit llm",
    )
    api_key: str = Field(default="", description="API key; empty uses llm.api_key")
    api_base: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1", description="API base; empty uses llm.api_base")
    request_params: Optional[Dict[str, Any]] = Field(default=None, description="Extra litellm.embedding params")
    enable_batch: bool = Field(default=False, description="Use batch async embedding when supported")
    batch_size: int = Field(default=20, description="Batch size")


class RerankerConfig(BaseModel):
    """LiteLLM rerank (``knowledge.vector_db.reranker``)."""

    model: str = Field(default="dashscope/qwen3-rerank", description="LiteLLM rerank model id")
    api_key: str = Field(default="", description="API key; empty uses llm.api_key")
    api_base: str = Field(default="https://dashscope.aliyuncs.com/compatible-api/v1/reranks", description="API base; empty uses llm.api_base")
    top_n: Optional[int] = Field(default=None, description="Cap reranked results")
    request_params: Optional[Dict[str, Any]] = Field(default=None, description="Extra litellm.rerank params")


class ChromaConfig(BaseModel):
    """Chroma vector store under ``knowledge.vector_db``."""

    collection: str = Field(default="docs", description="Collection name")
    name: str = Field(default="OpenFox Knowledge", description="Knowledge display name")
    description: str = Field(default="OpenFox Knowledge", description="Description")
    id: Optional[str] = Field(default=None, description="Optional Chroma instance id")
    distance: Distance = Field(default=Distance.cosine, description="Distance metric")
    persistent_client: bool = Field(default=True, description="Use Chroma persistent client")
    search_type: SearchType = Field(default=SearchType.vector, description="vector | keyword | hybrid")
    hybrid_rrf_k: int = Field(default=60, description="RRF k for hybrid search")
    batch_size: Optional[int] = Field(default=None, description="Chroma batch size")
    reranker_enabled: bool = Field(default=True, description="Attach LiteLLM reranker when true")
    embedder: EmbedderConfig = Field(default_factory=EmbedderConfig, description="Embedder")
    reranker: RerankerConfig = Field(default_factory=RerankerConfig, description="Reranker")


class KnowledgeConfig(BaseModel):
    """RAG / knowledge (active when ``search_knowledge`` is true)."""

    vector_db: ChromaConfig = Field(default_factory=ChromaConfig, description="Chroma + embedder/reranker")
    max_results: int = Field(default=10, description="Max chunks retrieved")
    isolate_vector_search: bool = Field(default=False, description="Isolate search when sharing one vector DB")


class ChannelsConfig(BaseModel):
    """Channel integrations."""

    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    wxclaw: WxClawConfig = Field(default_factory=WxClawConfig)

class MCPServerConfig(BaseModel):
    """MCP server connection (stdio or HTTP)."""

    name: str = Field(default="", description="Config display name")
    command: str = Field(default="", description="Command (stdio transport)")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    url: str = Field(default="", description="HTTP endpoint URL")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP custom headers")
    tool_timeout: int = Field(default=30, description="Tool call timeout in seconds")



class MCPConfig(ToolkitFilterFields):
    """OpenFox MCP server toolkit."""

    activate: bool = Field(default=True, description="Register MCP server tools")

class SchedulerConfig(ToolkitFilterFields):
    """OpenFox scheduled jobs: ``CronTools`` wraps Agno ``ScheduleManager``.

    JSON / env path: ``tools.scheduler``. When ``activate`` is false, the toolkit is not registered.
    Exposed tools: ``create``, ``list``, ``get``, ``delete``, ``disable`` (five-field cron → POST Agent run).
    """

    activate: bool = Field(default=True, description="Register CronTools (async schedule CRUD)")

class ShellConfig(ToolkitFilterFields):
    """Agno ``ShellTools`` — local shell (`Local → Shell <https://docs.agno.com/tools/toolkits/local/shell>`_)."""

    activate: bool = Field(default=True, description="Register this toolkit on the agent")
    base_dir: Optional[str] = Field(
        default=None,
        description="Working directory for subprocess (default: OpenFox process cwd)",
    )
    enable_run_shell_command: bool = Field(default=True, description="Expose run_shell_command")
    all: bool = Field(
        default=False,
        description="Agno ``all``: enable every shell tool (overrides flags when True)",
    )

class WebSearchConfig(ToolkitFilterFields):
    """Agno ``WebSearchTools`` — DDGS meta-search (`Search → Web Search <https://docs.agno.com/tools/toolkits/search/websearch>`_)."""

    activate: bool = Field(default=True, description="Register this toolkit on the agent")
    enable_search: bool = Field(default=True, description="Enable web search function")
    enable_news: bool = Field(default=True, description="Enable news search function")
    backend: str = Field(
        default="auto",
        description='Search backend (e.g. "auto", "duckduckgo", "google", "bing", "brave")',
    )
    modifier: Optional[str] = Field(default=None, description="String prepended to every query")
    fixed_max_results: Optional[int] = Field(default=None, description="Cap results (optional)")
    proxy: Optional[str] = Field(default=None, description="HTTP(S) proxy URL")
    timeout: Optional[int] = Field(default=10, description="Request timeout seconds")
    verify_ssl: bool = Field(default=True, description="Verify TLS certificates")
    timelimit: Optional[Literal["d", "w", "m", "y"]] = Field(
        default=None,
        description='Recency filter: day/week/month/year ("d","w","m","y")',
    )
    region: Optional[str] = Field(default=None, description='Region hint (e.g. "us-en", "uk-en")')


class ArxivConfig(ToolkitFilterFields):
    """Agno ``ArxivTools`` (`Search → Arxiv <https://docs.agno.com/tools/toolkits/search/arxiv>`_)."""

    activate: bool = Field(default=True, description="Register this toolkit on the agent")
    enable_search_arxiv: bool = Field(default=True, description="Enable arXiv search")
    enable_read_arxiv_papers: bool = Field(default=True, description="Enable reading arXiv papers (PDF helpers)")
    download_dir: Optional[str] = Field(
        default=None,
        description="Directory for downloaded PDFs (default: Agno package path)",
    )


class HackerNewsConfig(ToolkitFilterFields):
    """Agno ``HackerNewsTools`` (`Search → HackerNews <https://docs.agno.com/tools/toolkits/search/hackernews>`_)."""

    activate: bool = Field(default=True, description="Register this toolkit on the agent")
    enable_get_top_stories: bool = Field(default=True, description="Top stories tool")
    enable_get_user_details: bool = Field(default=True, description="HN user lookup tool")
    all: bool = Field(default=False, description="Agno ``all``")


class PubmedConfig(ToolkitFilterFields):
    """Fields match Agno ``PubmedTools`` params (`Search → Pubmed <https://docs.agno.com/tools/toolkits/search/pubmed>`_)."""

    activate: bool = Field(default=True, description="Register this toolkit on the agent")
    email: str = Field(
        default="your_email@example.com",
        description="Email sent with NCBI E-utilities requests (required by NCBI)",
    )
    max_results: Optional[int] = Field(
        default=None,
        description="Optional cap on the number of results (tool default may still apply per query)",
    )
    enable_search_pubmed: bool = Field(default=True, description="Enable the search_pubmed tool")
    all: bool = Field(
        default=False,
        description="Agno ``all``: enable all PubMed toolkit functionality",
    )


class WikipediaConfig(ToolkitFilterFields):
    """Agno ``WikipediaTools`` (`Search → Wikipedia <https://docs.agno.com/tools/toolkits/search/wikipedia>`_)."""

    activate: bool = Field(default=True, description="Register this toolkit on the agent")


class Crawl4aiConfig(ToolkitFilterFields):
    """Fields match Agno ``Crawl4aiTools`` params (`Web Scraping → Crawl4AI <https://docs.agno.com/tools/toolkits/web-scrape/crawl4ai>`_)."""

    activate: bool = Field(default=True, description="Register this toolkit on the agent")
    max_length: Optional[int] = Field(
        default=1000,
        description="Max length of returned page text (use ``null`` in JSON for no cap, per Agno cookbook)",
    )
    timeout: int = Field(default=60, description="Timeout in seconds for crawling")
    use_pruning: bool = Field(default=False, description="Enable content pruning for less relevant text")
    pruning_threshold: float = Field(default=0.48, description="Pruning relevance threshold")
    bm25_threshold: float = Field(default=1.0, description="BM25 relevance threshold")
    headless: bool = Field(default=True, description="Run browser headless")
    wait_until: str = Field(
        default="domcontentloaded",
        description='Playwright wait until event (e.g. "domcontentloaded", "load", "networkidle")',
    )
    enable_crawl: bool = Field(default=True, description="Enable the crawl tool")
    all: bool = Field(
        default=False,
        description="Agno ``all``: enable all functions; when True, other enable flags are ignored",
    )


class CalculatorConfig(ToolkitFilterFields):
    """Agno ``CalculatorTools`` math helpers (`Local → Calculator <https://docs.agno.com/tools/toolkits/local/calculator>`_)."""

    activate: bool = Field(default=True, description="Register this toolkit on the agent")


class DockerConfig(ToolkitFilterFields):
    """Agno ``DockerTools`` (`Local → Docker <https://docs.agno.com/tools/toolkits/local/docker>`_)."""

    activate: bool = Field(default=False, description="Register this toolkit on the agent")


class YouTubeConfig(ToolkitFilterFields):
    """OpenFox + Agno ``YouTubeTools`` — toolkit params follow the docs table (`Others → YouTube
    <https://docs.agno.com/tools/toolkits/others/youtube>`_): seven rows + ``activate`` for OpenFox.

    Agno's constructor takes ``enable_*`` / ``all`` / ``languages`` only; the doc's
    ``get_video_captions`` and ``get_video_data`` are combined with the matching ``enable_*`` flags
    when building kwargs (both must be true unless ``all`` is true).
    """

    activate: bool = Field(default=True, description="Register this toolkit on the agent")
    get_video_captions: bool = Field(
        default=True,
        description="Doc: enable retrieving video captions",
    )
    get_video_data: bool = Field(
        default=True,
        description="Doc: enable retrieving video metadata",
    )
    languages: Optional[List[str]] = Field(
        default=None,
        description="Preferred caption languages when applicable",
    )
    enable_get_video_captions: bool = Field(
        default=True,
        description="Doc: enable get_youtube_video_captions",
    )
    enable_get_video_data: bool = Field(
        default=True,
        description="Doc: enable get_youtube_video_data",
    )
    enable_get_video_timestamps: bool = Field(
        default=True,
        description="Doc: enable get_youtube_video_timestamps",
    )
    all: bool = Field(
        default=False,
        description="Doc: enable all functionality (Agno ``all``)",
    )


class WebBrowserConfig(ToolkitFilterFields):
    """OpenFox + Agno ``WebBrowserTools`` — params match the docs table (`Others → Web Browser
    <https://docs.agno.com/tools/toolkits/others/web-browser>`_): ``enable_open_page``, ``all``;
    plus ``activate`` to register the toolkit on the agent."""

    activate: bool = Field(default=True, description="Register this toolkit on the agent")
    enable_open_page: bool = Field(
        default=True,
        description="Doc: enables opening URLs in the system default browser",
    )
    all: bool = Field(
        default=False,
        description="Doc: enables all toolkit functionality when True (Agno ``all``)",
    )

class ToolsConfig(BaseModel):
    """Per-toolkit options for OpenFox (see `Toolkit index <https://docs.agno.com/tools/toolkits/overview>`_).

    Uses ``BaseModel`` so the host env var ``SHELL`` does not collide with toolkit settings.
    """
    mcp: MCPConfig = Field(default_factory=MCPConfig, description="MCP server (OpenFox)")
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig, description="Scheduler (CronTools; tools.scheduler)")
    shell: ShellConfig = Field(default_factory=ShellConfig, description="Shell (Agno)")
    websearch: WebSearchConfig = Field(default_factory=WebSearchConfig, description="Web search (Agno)")
    arxiv: ArxivConfig = Field(default_factory=ArxivConfig, description="Arxiv settings")
    hackernews: HackerNewsConfig = Field(default_factory=HackerNewsConfig, description="Hackernews settings")
    pubmed: PubmedConfig = Field(default_factory=PubmedConfig, description="Pubmed settings")
    wikipedia: WikipediaConfig = Field(default_factory=WikipediaConfig, description="Wikipedia settings")
    crawl4ai: Crawl4aiConfig = Field(default_factory=Crawl4aiConfig, description="Crawl4ai settings")
    calculator: CalculatorConfig = Field(default_factory=CalculatorConfig, description="Calculator settings")
    docker: DockerConfig = Field(default_factory=DockerConfig, description="Docker settings")
    youtube: YouTubeConfig = Field(default_factory=YouTubeConfig, description="YouTube settings")
    webbrowser: WebBrowserConfig = Field(default_factory=WebBrowserConfig, description="Webbrowser settings")

class Config(BaseSettings):
    """Application configuration."""

    agent_id: str = Field(default="OpenFox", description="Agent ID")
    docs_enabled: bool = Field(default=True, description="Enable API docs")
    os_security_key: str = Field(default="", description="AgentOS security key")
    cors_origin_list: List[str] = Field(
        default_factory=lambda: list(OPENFOX_EMBEDDED_WEB_CORS_ORIGINS),
        description="Allowed CORS origins (default includes embedded /web on port 7777)",
    )
    time_zone: str = Field(default="Asia/Shanghai", description="Default timezone")
    search_knowledge: bool = Field(default=False, description="Enable RAG (Chroma + Knowledge on the agent)")
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM settings")
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig, description="Knowledge / vector DB settings")
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig, description="Channel integrations")
    mcps: List[MCPServerConfig] = Field(default_factory=list, description="MCP server connections")
    tools: ToolsConfig = Field(default_factory=ToolsConfig, description="Tools settings")