<p align="center">
  <a href="./README.md">English</a> | <a href="./README-zh_CN.md">简体中文</a>
</p>

<p align="center">
  <img src="./assets/openfox-logo.png" alt="OpenFox logo" width="64" height="64" />
</p>

<p align="center">
  <strong>Self-hosted personal AI assistant</strong><br />
  Feishu channel · Built-in Web console · LiteLLM multi-model
</p>

<p align="center">
  <a href="https://docs.python.org/3.12/"><img src="https://img.shields.io/badge/python-3.12+-blue.svg?style=flat-square" alt="Python" /></a>
  <a href="https://github.com/agno-agi/agno"><img src="https://img.shields.io/badge/framework-agno-orange.svg?style=flat-square" alt="Agno" /></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/API-FastAPI-009688.svg?style=flat-square" alt="FastAPI" /></a>
</p>

---

## What it is

**OpenFox** runs on your own machine: it brings **LLM chat, scheduled jobs, Feishu bot, browser tools, MCP, and local skills** together in one HTTP service. It ships with an **embedded Web UI** at `/web`, and you can also talk to the assistant from Feishu.

| Path | Description |
|------|-------------|
| `~/.openfox/config.json` | LLM, Feishu, `cors_origin_list`, MCP, and related settings |
| `~/.openfox/storage.db` | **SQLite** storage for sessions and scheduling |
| `~/.openfox/skills` | Local **Skills** root (`SKILLS_PATH` in `openfox/utils/const.py`); on first run, if missing, copied from packaged `openfox/skills` (see `openfox/core/skills.py`) |

---

## Features

| Capability | Description |
|------------|-------------|
| **Web console** | Chat, session list, usage metrics, skill upload/management, Cron scheduling, JSON config editor (login required; use `os_security_key` from config) |
| **Feishu** | Event and message intake; DM and group chat (mention the bot) |
| **Scheduled jobs** | Built-in scheduler; create recurring tasks in natural language (CronTools) with callbacks to Agent endpoints |
| **Tools** | See “Built-in Agent tools” below; you can also attach **MCP** via `config.mcps`. JSON config editing in the Web console uses **ConfigTools** (not an Agent chat tool). |
| **Skills** | `SKILL.md` under `SKILLS_PATH` (`~/.openfox/skills`, LocalSkills); upload skill packs from the Web UI |
| **Models** | **LiteLLM** for OpenAI-compatible APIs (see “Models” below) |

---

## Built-in Agent tools

| Tool class | What it does |
|------------|----------------|
| **ShellTools** | Run shell commands on the host where OpenFox runs (Agno) |
| **CronTools** | Create / list scheduled jobs; Cron expressions invoke this Agent's run endpoint |
| **BrowserTools** | Local Chromium **remote debugging (CDP)**: launch or reuse the browser, health checks, get DevTools WebSocket, stop the process—for automation / Playwright, etc. |
| **FeishuTools** | Feishu-related actions (e.g. messaging with the channel) |
| **MCPConfigTools** | Add / remove / update MCP-related config in chat to extend tools dynamically |
| **WebSearchTools** | Search the web |
| **ArxivTools** | Search [arXiv](https://arxiv.org/) papers and metadata |
| **HackerNewsTools** | Read Hacker News stories and discussions |
| **PubmedTools** | Search [PubMed](https://pubmed.ncbi.nlm.nih.gov/) biomedical literature |
| **WikipediaTools** | Look up Wikipedia articles and summaries |
| **Crawl4aiTools** | Fetch and parse page content with Crawl4AI (suited to structured extraction) |
| **CalculatorTools** | Evaluate math expressions |
| **DockerTools** | Manage local Docker: containers, images, volumes, networks (Docker must be available) |
| **YouTubeTools** | YouTube: metadata, captions, timestamps, etc. (requires `youtube_transcript_api`) |
| **WebBrowserTools** | Open a URL in the **system default browser** on this machine (new tab or new window) |

---

## Quick start

**Environment**: Python **3.12+**. Install dependencies with [uv](https://github.com/astral-sh/uv) from the repo root.

```bash
uv sync   # or: pip install -e .
```

**First run**: If `~/.openfox/config.json` is missing, an interactive setup runs (API docs toggle, auth, `os_security_key`, timezone, LLM, Feishu, etc.), then the server starts.

```bash
python -m openfox
# Binds to 0.0.0.0:7777 by default
```

For custom `--host` / `--port`, run `python -m openfox --help` for CLI subcommands and flags.

- **Web UI**: Open `http://127.0.0.1:7777/web` (adjust port as needed).
- **Auth token**: The `os_security_key` value from config; enter it on the Web login page.
- **Non-7777 ports**: Default CORS includes `/web` on `:7777`. If you change the port, add e.g. `http://127.0.0.1:<port>` and `http://localhost:<port>` to `cors_origin_list`, or the frontend may fail API calls.

To re-run setup only, delete `~/.openfox/config.json` and run `python -m openfox` again. Existing config skips the wizard and starts directly.

---

## Feishu integration

Request path prefix is **`/feishu`**.

- Event / webhook example: `http://<your-host-or-domain>/feishu/event` (match whatever Feishu Open Platform expects and your routes).

Steps in brief:

1. Create an app on [Feishu Open Platform](https://open.feishu.cn/) and obtain **App ID** and **App Secret**.
2. Configure event subscription and message permissions; set the request URL to your service (public URL or tunnel); fill **Encrypt Key** and **Verification Token**.
3. Write these into `channels.feishu` in `~/.openfox/config.json`, then restart `python -m openfox`.
4. In Feishu DM or group chat, use the app (e.g. @ bot) to talk to OpenFox.

---

## Models (LiteLLM)

OpenFox uses **LiteLLM**. For any provider in [LiteLLM’s supported list](https://docs.litellm.ai/docs/providers) that exposes an OpenAI-style Chat Completions API, you usually only need `llm.model_name`, `llm.api_base`, and `llm.api_key`.

Example model strings (see official docs for the full list):

```text
openai/gpt-4o-mini
deepseek/deepseek-chat
dashscope/qwen-max
ollama/llama3.1
...
```

---

## Screenshots

### Feishu

![feishu](./assets/feishu.gif)

### Web UI

<p align="center"><strong>Chat</strong></p>
<p align="center"><img src="./assets/image1.png" alt="OpenFox Web — Chat" width="900" /></p>

<p align="center"><strong>Sessions</strong></p>
<p align="center"><img src="./assets/image2.png" alt="OpenFox Web — Sessions" width="900" /></p>

<p align="center"><strong>Usage</strong></p>
<p align="center"><img src="./assets/image3.png" alt="OpenFox Web — Usage" width="900" /></p>

<p align="center"><strong>Skills</strong></p>
<p align="center"><img src="./assets/image4.png" alt="OpenFox Web — Skills" width="900" /></p>

<p align="center"><strong>Scheduled jobs</strong></p>
<p align="center"><img src="./assets/image5.png" alt="OpenFox Web — Cron" width="900" /></p>

<p align="center"><strong>Config</strong></p>
<p align="center"><img src="./assets/image6.png" alt="OpenFox Web — Config" width="900" /></p>

---

## Intranet tunnel (optional)

- [zeronews](https://user.zeronews.cc/setup/start)

---

## Brief comparison with OpenClaw

| Aspect | OpenClaw | OpenFox |
|--------|----------|---------|
| Stack | Node / TypeScript | Python, Agno, FastAPI |
| Channels | Many IM platforms | Feishu-first (extensible) |
| Extensions | Browser, Canvas, Cron, etc. | Cron, Shell, browser (Playwright), MCP, local Skills |
| Focus | Cross-platform personal assistant | Self-hosted, bilingual-friendly, lightweight control plane with integrated Web UI |

---

## Thanks & community

> Stars help us keep improving.

### Community chat

When joining, say you’re here for **openfox**:

<p align="center">
  <img src="./assets/kylin.png" width="220" alt="Community QR" />
</p>
