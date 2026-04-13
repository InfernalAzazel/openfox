/**
 * 将内部 Session 行 / 运行解析结果转为 agent-ui 的 {@link ChatMessage} 列表
 * @see https://github.com/agno-agi/agent-ui/blob/main/src/types/os.ts ChatMessage
 */
import type { AssistantToolCallTag, SessionChatLine } from '@/types/chat'
import type { ChatMessage, ToolCall } from '@/types/os'

function assistantTagsToToolCalls(
  tags: AssistantToolCallTag[],
  outputs: string[] | undefined,
  createdAt: number,
): ToolCall[] {
  return tags.map((tag, i) => {
    const tool_args: Record<string, string> = {}
    const raw = tag.arguments?.trim()
    if (raw) {
      try {
        const o = JSON.parse(raw) as Record<string, unknown>
        for (const [k, v] of Object.entries(o)) {
          tool_args[k] =
            typeof v === 'string'
              ? v
              : v == null || v === undefined
                ? ''
                : JSON.stringify(v)
        }
      } catch {
        tool_args._raw = raw
      }
    }
    const out = outputs?.[i]?.trim()
    return {
      role: 'assistant' as const,
      content: out ?? null,
      tool_call_id: tag.id ?? `call-${i}-${tag.name}`,
      tool_name: tag.name,
      tool_args,
      tool_call_error: false,
      metrics: { time: 0 },
      created_at: createdAt,
    }
  })
}

export function sessionLinesToChatMessages(
  lines: SessionChatLine[],
): ChatMessage[] {
  const out: ChatMessage[] = []
  let i = 0
  for (const line of lines) {
    const created_at = Date.now() + i
    i += 1
    if (line.role === 'user') {
      out.push({ role: 'user', content: line.body, created_at })
    } else if (line.role === 'tool') {
      out.push({ role: 'tool', content: line.body, created_at })
    } else {
      const tool_calls = line.toolCalls?.length
        ? assistantTagsToToolCalls(
            line.toolCalls,
            line.toolOutputs,
            created_at,
          )
        : undefined
      out.push({
        role: 'agent',
        content: line.body,
        created_at,
        tool_calls: tool_calls?.length ? tool_calls : undefined,
      })
    }
  }
  return out
}

export function agentReplyToChatMessage(
  content: string,
  toolCalls: AssistantToolCallTag[] | undefined,
  created_at: number = Date.now(),
  toolOutputs?: string[],
): ChatMessage {
  const tool_calls = toolCalls?.length
    ? assistantTagsToToolCalls(toolCalls, toolOutputs, created_at)
    : undefined
  return {
    role: 'agent',
    content,
    created_at,
    tool_calls: tool_calls?.length ? tool_calls : undefined,
  }
}
