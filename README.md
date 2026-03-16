# OpenFox — 你的个人 AI 助手

**OpenFox** 是你在自己设备上运行的**个人 AI 助手**。通过飞书等通道与它对话，它可以使用定时任务、股票行情、Shell、MCP 工具和本地技能来帮你完成任务。网关即控制面，产品即助手。

如果你想要一个**自托管、单用户、本地优先**的 AI 助手，就是它。

---

## 推荐安装方式

**运行环境：Python ≥3.12**。推荐使用 [uv](https://github.com/astral-sh/uv) 或 pip + venv。

```bash
# 克隆并进入项目
git clone https://github.com/你的账号/openfox.git
cd openfox

# 使用 uv 安装（推荐）
uv sync

# 或使用 pip
pip install -e .
```

---

## 快速开始（TL;DR）

**首次运行会自动生成默认配置**（`~/.openfox/config.json`），无需手动创建。

```bash
# 启动 HTTP 服务（默认端口 7777）
python -m openfox serve
```

服务启动后：

- **飞书**：在飞书开放平台配置事件订阅与消息回调，指向该服务的飞书接口地址即可与助手对话。
- **定时任务**：在对话中说「每 5 分钟提醒我喝水」等，Agent 会通过 Cron 工具创建周期任务。
- **终端交互**（规划中）：`python -m openfox agent` 将提供 REPL 与助手对话。

升级或排查问题时，可检查 `~/.openfox/config.json` 与 MongoDB 连接、LLM API 配置是否正确。

---

## 功能亮点

- **本地优先网关** — 单控制面：会话、通道、工具与定时任务统一管理。
- **飞书通道** — 在飞书中与助手对话，支持单聊与群聊（可扩展更多通道）。
- **定时任务（Cron）** — 用自然语言创建周期任务（如「每天早上 9 点发日报」），到点自动回调 Agent。
- **丰富工具** — Shell 执行、AkShare 股票行情、MCP 工具集、配置读写；技能文档中的 CLI 示例可由 Agent 调用执行。
- **技能与 MCP** — 本地 Skills（`openfox/skills`）+ 可配置 MCP server（stdio/HTTP），按需扩展能力。
- **配置即服务** — 配置文件 `~/.openfox/config.json`，支持通过 Agent 的 config 工具在对话中查看与修改。

---
## 效果

![feishu](./assets/feishu.gif)

## 架构示意

```
飞书 / 其他通道（未来）
        │
        ▼
┌───────────────────────────────┐
│     OpenFox HTTP 服务         │
│     (FastAPI, 默认 :7777)     │
└──────────────┬────────────────┘
               │
               ├─ Agno Agent (id: openfox)
               ├─ 飞书接口
               ├─ 调度器（MongoDB）
               └─ 工具：Cron / Shell / AkShare / MCP / Config
```

---

## 配置说明

最小配置示例（`~/.openfox/config.json`）：

```json
{
  "db_url": "mongodb://localhost:27017",
  "llm": {
    "model_name": "dashscope/qwen-max",
    "api_key": "your-api-key",
    "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1"
  },
  "channels": {
    "feishu": {
      "app_id": "",
      "app_secret": "",
      "encrypt_key": "",
      "verification_token": ""
    }
  },
  "mcps": []
}
```

- **db_url**：MongoDB 连接字符串（会话与调度存储）。
- **llm**：模型名称、API Key、API Base（兼容 OpenAI 的接口即可，如 DashScope、LiteLLM）。
- **channels.feishu**：飞书开放平台应用凭证与事件订阅密钥。
- **mcps**：MCP server 列表，每项可为 `command`+`args`（stdio）或 `url`（HTTP）。

完整配置字段见 `openfox/modes/config.py`。

---

## 飞书接入

1. 在 [飞书开放平台](https://open.feishu.cn/) 创建应用，获取 **App ID**、**App Secret**。
2. 开启「事件订阅」与「消息与群组」等权限，配置请求地址：`https://你的域名/openfox/feishu`（或内网穿透地址），并填写 **Encrypt Key**、**Verification Token**。
3. 将上述信息写入 `~/.openfox/config.json` 的 `channels.feishu`，重启 `openfox serve`。
4. 在飞书中拉群或单聊，@ 机器人或私聊即可与 OpenFox 助手对话。

---

## 技能与工作区

- **技能目录**：`openfox/skills/`，每个子目录可包含 `SKILL.md`，由 Agno 的 `LocalSkills` 自动加载。
- **MCP 工具**：在配置的 `mcps` 中声明 MCP server（stdio 或 HTTP），Agent 即可在对话中按需调用。
- 可在对话中通过 **config / mcp_config** 类工具查看或修改配置（修改 MCP 后需重启服务生效）。

---

## 与 OpenClaw 的对比

[OpenClaw](https://github.com/openclaw/openclaw) 是「Your own personal AI assistant. Any OS. Any Platform.」—— 多通道、多端、本地优先。OpenFox 与之类似，但更聚焦：

| 维度       | OpenClaw              | OpenFox                    |
|------------|------------------------|----------------------------|
| 技术栈     | Node/TypeScript        | Python + Agno + FastAPI    |
| 通道       | WhatsApp/Telegram/Slack/飞书等 20+ | 飞书（可扩展）             |
| 工具/扩展  | 内置浏览器、Canvas、Cron 等 | Cron、Shell、AkShare、MCP、Skills |
| 定位       | 全平台个人助手         | 自托管、中文场景、轻量中控 |

适合：希望用 **Python 生态** 自建一个类似 OpenClaw 的「单网关 + 多工具 + 飞书」助手的用户。

---

## 开发与从源码运行

```bash
git clone https://github.com/你的账号/openfox.git
cd openfox
uv sync

# 开发时直接跑服务
uv run python -m openfox serve
```

关键目录：

- `openfox/utils/agent.py` — Agent、工具、调度、飞书接口与 FastAPI 应用组装。
- `openfox/cli/commands.py` — CLI 入口（`serve` / `agent`）。
- `openfox/modes/config.py` — 配置模型。
- `openfox/tools/` — 各类工具实现。
- `openfox/skills/` — 技能与 SKILL.md。

---

## 加群

- 加微拉你入群
- 加群请注明来意: 留言 openfox

![wechat](./assets/kylin.png)
