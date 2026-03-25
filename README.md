<div align="center"><h1>🦊 OpenFox — 个人人工智能助手</h1></div>

<div align="center">

自托管轻量 AI 助手，多工具与飞书通道支持

[![python](https://img.shields.io/badge/python-3.12.x-blue.svg?style=flat-square)](https://docs.python.org/3.12/index.html)
[![agno](https://img.shields.io/badge/agno-orange.svg?style=flat-square)](https://github.com/agno-agi/agno.git)
[![mongodb](https://img.shields.io/badge/mongodb-8-brightgreen.svg?style=flat-square)](https://github.com/mongodb/mongo.git)

</div>


**OpenFox** 是一款运行在您自己的设备上的**个人 AI 助手**。通过飞书等通道与它对话，它可以使用定时任务、股票行情、Shell、MCP 工具和本地技能来帮你完成任务。网关即控制面，产品即助手。
如果你想要一个**自托管、单用户、本地优先**的 AI 助手，就是它。

---

> 你的加🌟是我更新的动力

## 功能亮点

- **本地优先网关** — 单控制面：会话、通道、工具与定时任务统一管理。
- **飞书通道** — 在飞书中与助手对话，支持单聊与群聊（可扩展更多通道）。
- **定时任务（Cron）** — 用自然语言创建周期任务（如「每天早上 9 点发日报」），到点自动回调 Agent。
- **丰富工具** — Shell 执行、AkShare 股票行情、MCP 工具集、配置读写；技能文档中的 CLI 示例可由 Agent 调用执行。
- **技能与 MCP** — 本地 Skills（`openfox/skills`）+ 可配置 MCP server（stdio/HTTP），按需扩展能力。
- **配置即服务** — 配置文件 `~/.openfox/config.json`，支持通过 Agent 的 config 工具在对话中查看与修改。

---


## 快速开始（TL;DR）

**首次运行会自动生成默认配置**（`~/.openfox/config.json`），无需手动创建。

```bash
# 启动 HTTP 服务（默认端口 7777）
python -m openfox

🦊 初始化 OpenFox 配置
是否启用文档 (docs_enabled) [True]: 
是否启用授权 (authorization_enabled) [True]:
生成 token: 7a151a32b18b95735c327e82bf23ad49 
CORS 允许的源列表 (cors_origin_list, 用逗号分隔, 默认 * 表示所有源) [['*']]:
时区 (time_zone) [Asia/Shanghai]: 

配置 LLM：
LLM 模型名称 (llm.model_name) [deepseek/deepseek-chat]: 
LLM API Base URL (llm.api_base) [https://api.deepseek.com]: 
LLM API Key (llm.api_key): 你的 Key

配置飞书通道：
飞书 App ID (channels.feishu.app_id): 你的 App ID 
飞书 App Secret (channels.feishu.app_secret): 你的 App Secret
飞书 Encrypt Key (channels.feishu.encrypt_key): 你的 Encrypt Key
飞书 Verification Token (channels.feishu.verification_token): 你的 Verification Token
配置文件已保存到：/Users/kylin/.openfox/config.json
```

服务启动后：

- **飞书**：在飞书开放平台配置事件订阅与消息回调，指向该服务的飞书接口地址即可与助手对话。
- **定时任务**：在对话中说「每 5 分钟提醒我喝水」等，Agent 会通过 Cron 工具创建周期任务。

升级或排查问题时，可检查 `~/.openfox/config.json` 与 MongoDB 连接、LLM API 配置是否正确。

---

## 支持模型

- [LiteLLM 支持的所有 OpenAI-compatible 提供商与模型](https://docs.litellm.ai/docs/providers)，只要走 OpenAI Chat Completions 接口基本都能用。

```text
示例模型（仅示例，完整列表见上方链接）：
- openai/gpt-4.1-mini
- openai/gpt-4.1
- openai/gpt-4.1-preview
- openai/gpt-4o-mini
- openai/gpt-4o
- dashscope/qwen-max
- deepseek/deepseek-chat
- moonshot/moonshot-v1-32k
- ollama/llama3.1
- openrouter/meta-llama/Meta-Llama-3.1-70B-Instruct
```
---

## 效果

![feishu](./assets/feishu.gif)

---

## 内网穿透工具

- [zeronews](https://user.zeronews.cc/setup/start)

## 飞书接入

- webhook url http//:你的ip地址/feishu/event

1. 在 [飞书开放平台](https://open.feishu.cn/) 创建应用，获取 **App ID**、**App Secret**。
2. 开启「事件订阅」与「消息与群组」等权限，配置请求地址：`https://你的域名/openfox/feishu`（或内网穿透地址），并填写 **Encrypt Key**、**Verification Token**。
3. 将上述信息写入 `~/.openfox/config.json` 的 `channels.feishu`，重启 `openfox serve`。
4. 在飞书中拉群或单聊，@ 机器人或私聊即可与 OpenFox 助手对话。

---

## 技能与工作区

- **技能目录**：`openfox/skills/`，每个子目录可包含 `SKILL.md`，由 Agno 的 `LocalSkills` 自动加载。
- **MCP 工具**：在配置的 `mcps` 中声明 MCP server（stdio 或 HTTP），Agent 即可在对话中按需调用。

---

## 与 OpenClaw 的对比

| 维度       | OpenClaw              | OpenFox                    |
|------------|------------------------|----------------------------|
| 技术栈     | Node/TypeScript        | Python + Agno + FastAPI    |
| 通道       | WhatsApp/Telegram/Slack/飞书等 20+ | 飞书（可扩展）             |
| 工具/扩展  | 内置浏览器、Canvas、Cron 等 | Cron、Shell、AkShare、MCP、Skills |
| 定位       | 全平台个人助手         | 自托管、中文场景、轻量中控 |

---


## 加群

- 加群请注明来意: 留言 openfox

<img src="assets/kylin.png" width="220" alt="220" />
