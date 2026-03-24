from typing import Any
from agno.tools import Toolkit
from json_repair import loads as json_repair_loads
from openfox.schemas.config import MCPServerConfig
from openfox.tools.config import ConfigTools


class MCPConfigTools(Toolkit):
    """MCP configuration tools: view, add, and remove MCP configurations."""

    def __init__(self, config_tools: ConfigTools | None = None) -> None:
        self._config_tools = config_tools or ConfigTools()
        super().__init__(
            name="mcp_config",
            tools=[
                self.list_mcps,
                self.add_mcp_stdio,
                self.add_mcp_http,
                self.edit_mcp,
                self.remove_mcp,
                self.clear_mcps,
            ],
        )

    def list_mcps(self) -> list[dict[str, Any]]:
        """View the current MCP configuration."""
        cfg = self._config_tools.load()
        return [item.model_dump(by_alias=False) for item in cfg.mcps]

    def add_mcp_stdio(
        self,
        name: str,
        command: str,
        args: str = "[]",
        env: str = "{}",
        tool_timeout: int = 30,
    ) -> str:
        """Add a stdio MCP configuration.

        Args:
            name: MCP configuration name, used for deletion and identification.
            command: Executable command, e.g. `npx`.
            args: JSON string of an array, e.g. `[\"mcp-server-weibo\"]`.
            env: JSON string of an object, e.g. `{\"HTTP_PROXY\":\"http://127.0.0.1:7890\"}`.
            tool_timeout: Tool timeout in seconds.
        """
        cfg = self._config_tools.load()

        parsed_args = json_repair_loads(args) if args else []
        parsed_env = json_repair_loads(env) if env else {}
        if not isinstance(parsed_args, list):
            raise ValueError("args must be a JSON array string")
        if not isinstance(parsed_env, dict):
            raise ValueError("env must be a JSON object string")

        cfg.mcps = [m for m in cfg.mcps if m.name != name]
        cfg.mcps.append(
            MCPServerConfig(
                name=name,
                command=command,
                args=[str(x) for x in parsed_args],
                env={str(k): str(v) for k, v in parsed_env.items()},
                tool_timeout=tool_timeout,
            )
        )
        self._config_tools.save(cfg)
        return f"stdio MCP added: {name}. Restart the service for changes to take effect."

    def add_mcp_http(
        self,
        name: str,
        url: str,
        headers: str = "{}",
        tool_timeout: int = 30,
    ) -> str:
        """Add an HTTP MCP configuration.

        Args:
            name: MCP configuration name, used for deletion and identification.
            url: Streamable HTTP endpoint URL.
            headers: JSON string of an object, e.g. `{\"Authorization\":\"Bearer xxx\"}`.
            tool_timeout: Tool timeout in seconds.
        """
        cfg = self._config_tools.load()

        parsed_headers = json_repair_loads(headers) if headers else {}
        if not isinstance(parsed_headers, dict):
            raise ValueError("headers must be a JSON object string")

        cfg.mcps = [m for m in cfg.mcps if m.name != name]
        cfg.mcps.append(
            MCPServerConfig(
                name=name,
                url=url,
                headers={str(k): str(v) for k, v in parsed_headers.items()},
                tool_timeout=tool_timeout,
            )
        )
        self._config_tools.save(cfg)
        return f"HTTP MCP added: {name}. Restart the service for changes to take effect."

    def remove_mcp(self, name: str) -> str:
        """Remove an MCP configuration by name."""
        cfg = self._config_tools.load()
        before = len(cfg.mcps)
        cfg.mcps = [m for m in cfg.mcps if m.name != name]
        after = len(cfg.mcps)
        if before == after:
            return f"MCP not found: {name}"
        self._config_tools.save(cfg)
        return f"MCP removed: {name}. Restart the service for changes to take effect."

    def edit_mcp(
        self,
        name: str,
        command: str = "",
        args: str = "",
        env: str = "",
        url: str = "",
        headers: str = "",
        tool_timeout: int = 0,
    ) -> str:
        """Edit an existing MCP configuration (matched by name).

        Only fields that are passed in are updated; omitted values (empty string / 0)
        keep the previous values.

        Args:
            name: Name of an existing MCP configuration.
            command: New command (stdio), e.g. `npx`.
            args: New args as a JSON array string, e.g. `[\"mcp-server-weibo\"]`.
            env: New environment variables as a JSON object string.
            url: New HTTP endpoint URL.
            headers: New HTTP headers as a JSON object string.
            tool_timeout: New timeout in seconds; <= 0 means do not change.
        """
        cfg = self._config_tools.load()
        idx = next((i for i, m in enumerate(cfg.mcps) if m.name == name), -1)
        if idx < 0:
            return f"MCP not found: {name}"

        current = cfg.mcps[idx].model_dump(by_alias=False)

        # Read and update structured fields
        if args:
            parsed_args = json_repair_loads(args)
            if not isinstance(parsed_args, list):
                raise ValueError("args must be a JSON array string")
            current["args"] = [str(x) for x in parsed_args]
        if env:
            parsed_env = json_repair_loads(env)
            if not isinstance(parsed_env, dict):
                raise ValueError("env must be a JSON object string")
            current["env"] = {str(k): str(v) for k, v in parsed_env.items()}
        if headers:
            parsed_headers = json_repair_loads(headers)
            if not isinstance(parsed_headers, dict):
                raise ValueError("headers must be a JSON object string")
            current["headers"] = {str(k): str(v) for k, v in parsed_headers.items()}

        # Update simple scalar fields
        if command:
            current["command"] = command
        if url:
            current["url"] = url
        if tool_timeout > 0:
            current["tool_timeout"] = tool_timeout

        # Mutually exclusive: stdio vs HTTP—only one transport
        has_command = bool(current.get("command"))
        has_url = bool(current.get("url"))
        if has_command and has_url:
            # Prefer the transport explicitly changed in this call
            if command and not url:
                current["url"] = ""
                current["headers"] = {}
            elif url and not command:
                current["command"] = ""
                current["args"] = []
                current["env"] = {}
            else:
                raise ValueError(
                    "command and url cannot both be set; keep only one MCP transport"
                )

        cfg.mcps[idx] = MCPServerConfig.model_validate(current)
        self._config_tools.save(cfg)
        return f"MCP updated: {name}. Restart the service for changes to take effect."

    def clear_mcps(self) -> str:
        """Clear all MCP configurations."""
        cfg = self._config_tools.load()
        cfg.mcps = []
        self._config_tools.save(cfg)
        return "All MCP configurations cleared. Restart the service for changes to take effect."
