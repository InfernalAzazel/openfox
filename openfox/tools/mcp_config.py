from typing import Any
from agno.tools import Toolkit
from json_repair import loads as json_repair_loads
from openfox.modes.config import MCPServerConfig
from openfox.tools.config import ConfigTools


class MCPConfigTools(Toolkit):
    """MCP 配置工具：查看、新增、删除 MCP 配置。"""

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
        """查看当前 MCP 配置。"""
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
        """新增 stdio MCP 配置。

        Args:
            name: MCP 配置名称，用于删除和识别。
            command: 可执行命令，如 `npx`。
            args: JSON 字符串数组，如 `[\"mcp-server-weibo\"]`。
            env: JSON 字符串对象，如 `{\"HTTP_PROXY\":\"http://127.0.0.1:7890\"}`。
            tool_timeout: 工具超时秒数。
        """
        cfg = self._config_tools.load()

        parsed_args = json_repair_loads(args) if args else []
        parsed_env = json_repair_loads(env) if env else {}
        if not isinstance(parsed_args, list):
            raise ValueError("args 必须是 JSON 数组字符串")
        if not isinstance(parsed_env, dict):
            raise ValueError("env 必须是 JSON 对象字符串")

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
        return f"已添加 stdio MCP：{name}。请重启服务使其生效。"

    def add_mcp_http(
        self,
        name: str,
        url: str,
        headers: str = "{}",
        tool_timeout: int = 30,
    ) -> str:
        """新增 HTTP MCP 配置。

        Args:
            name: MCP 配置名称，用于删除和识别。
            url: Streamable HTTP 端点 URL。
            headers: JSON 字符串对象，如 `{\"Authorization\":\"Bearer xxx\"}`。
            tool_timeout: 工具超时秒数。
        """
        cfg = self._config_tools.load()

        parsed_headers = json_repair_loads(headers) if headers else {}
        if not isinstance(parsed_headers, dict):
            raise ValueError("headers 必须是 JSON 对象字符串")

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
        return f"已添加 HTTP MCP：{name}。请重启服务使其生效。"

    def remove_mcp(self, name: str) -> str:
        """按名称删除 MCP 配置。"""
        cfg = self._config_tools.load()
        before = len(cfg.mcps)
        cfg.mcps = [m for m in cfg.mcps if m.name != name]
        after = len(cfg.mcps)
        if before == after:
            return f"未找到 MCP：{name}"
        self._config_tools.save(cfg)
        return f"已删除 MCP：{name}。请重启服务使其生效。"

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
        """编辑已存在的 MCP 配置（按 name 匹配）。

        仅更新传入的字段；未传入（空字符串/0）则保持原值。

        Args:
            name: 已存在的 MCP 配置名称。
            command: 新命令（stdio），如 `npx`。
            args: 新参数 JSON 数组字符串，如 `[\"mcp-server-weibo\"]`。
            env: 新环境变量 JSON 对象字符串。
            url: 新 HTTP 端点 URL。
            headers: 新 HTTP 头 JSON 对象字符串。
            tool_timeout: 新超时秒数，<=0 表示不修改。
        """
        cfg = self._config_tools.load()
        idx = next((i for i, m in enumerate(cfg.mcps) if m.name == name), -1)
        if idx < 0:
            return f"未找到 MCP：{name}"

        current = cfg.mcps[idx].model_dump(by_alias=False)

        # 读取并更新结构化字段
        if args:
            parsed_args = json_repair_loads(args)
            if not isinstance(parsed_args, list):
                raise ValueError("args 必须是 JSON 数组字符串")
            current["args"] = [str(x) for x in parsed_args]
        if env:
            parsed_env = json_repair_loads(env)
            if not isinstance(parsed_env, dict):
                raise ValueError("env 必须是 JSON 对象字符串")
            current["env"] = {str(k): str(v) for k, v in parsed_env.items()}
        if headers:
            parsed_headers = json_repair_loads(headers)
            if not isinstance(parsed_headers, dict):
                raise ValueError("headers 必须是 JSON 对象字符串")
            current["headers"] = {str(k): str(v) for k, v in parsed_headers.items()}

        # 更新简单字段
        if command:
            current["command"] = command
        if url:
            current["url"] = url
        if tool_timeout > 0:
            current["tool_timeout"] = tool_timeout

        # 互斥：stdio 与 HTTP 配置二选一
        has_command = bool(current.get("command"))
        has_url = bool(current.get("url"))
        if has_command and has_url:
            # 优先保持本次显式修改的 transport
            if command and not url:
                current["url"] = ""
                current["headers"] = {}
            elif url and not command:
                current["command"] = ""
                current["args"] = []
                current["env"] = {}
            else:
                raise ValueError("command/url 不能同时有效，请只保留一种 MCP 传输方式")

        cfg.mcps[idx] = MCPServerConfig.model_validate(current)
        self._config_tools.save(cfg)
        return f"已更新 MCP：{name}。请重启服务使其生效。"

    def clear_mcps(self) -> str:
        """清空全部 MCP 配置。"""
        cfg = self._config_tools.load()
        cfg.mcps = []
        self._config_tools.save(cfg)
        return "已清空全部 MCP 配置。请重启服务使其生效。"

