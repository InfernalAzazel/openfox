---
name: summarize
description: 对 URL、播客和本地文件进行摘要或提取文本/字幕（适用于「给这个 YouTube/视频转文字」等场景）。
license: MIT
metadata:
  version: "1.0.0"
  author: openfox
  tags: ["summarize", "url", "youtube", "transcript", "cli"]
  homepage: https://summarize.sh
---

# Summarize

用于快速摘要 URL、本地文件和 YouTube 链接的 CLI 工具。

## 如何执行（Execution）

- 本技能通过**系统已安装的 CLI 可执行文件** `summarize` 完成（如通过 `brew install steipete/tap/summarize` 安装）。
- **不要**在本技能目录中寻找 `summarize.sh` 或其它脚本；应直接调用 **bash（或 run_shell）工具**，在 shell 中执行下面示例里的命令。
- 正确做法：先根据用户给的 URL/文件构造命令，再调用 bash 工具执行，例如：`summarize "https://用户提供的链接"`，将命令输出返回给用户。

## When to Use（使用时机）

当用户出现以下任一表述时，应立即使用本技能：
- 「用 summarize.sh」
- 「这个链接/视频讲的是什么？」
- 「摘要这个 URL/文章」
- 「给这个 YouTube/视频转文字」（尽力提取字幕，无需 `yt-dlp`）

## 快速开始

```bash
summarize "https://example.com"
summarize "https://example.com" --model google/gemini-3-flash-preview
summarize "/path/to/file.pdf" --model google/gemini-3-flash-preview
summarize "https://youtu.be/dQw4w9WgXcQ" --youtube auto
```

## YouTube：摘要 vs 字幕

仅对 URL 做尽力而为的字幕提取：

```bash
summarize "https://youtu.be/dQw4w9WgXcQ" --youtube auto --extract-only
```

若用户要的是字幕但内容很长，可先返回简短摘要，再询问要展开哪一段或哪个时间范围。

## 模型与 API Key

为所选服务商设置 API Key：
- OpenAI：`OPENAI_API_KEY`
- Anthropic：`ANTHROPIC_API_KEY`
- xAI：`XAI_API_KEY`
- Google：`GEMINI_API_KEY`（别名：`GOOGLE_GENERATIVE_AI_API_KEY`、`GOOGLE_API_KEY`）

未设置时默认模型为 `google/gemini-3-flash-preview`。

## 常用参数

- `--length short|medium|long|xl|xxl|<字符数>`
- `--max-output-tokens <数量>`
- `--extract-only`（仅 URL）
- `--json`（机器可读输出）
- `--firecrawl auto|off|always`（备用抓取）
- `--youtube auto`（若已设置 `APIFY_API_TOKEN`，可作为 YouTube 备用方案）

## 配置

可选配置文件：`~/.summarize/config.json`

```json
{ "model": "openai/gpt-5.2" }
```

可选服务：
- `FIRECRAWL_API_KEY`：用于难以直接抓取的站点
- `APIFY_API_TOKEN`：用于 YouTube 备用方案
