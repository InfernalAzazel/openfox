"""从应用配置构造 Agno MultiMCPTools。"""

from typing import Optional

from agno.tools.mcp import MultiMCPTools
from agno.tools.mcp.params import StreamableHTTPClientParams
from mcp import StdioServerParameters

from openfox.schemas.config import Config


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
