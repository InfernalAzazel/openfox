/**
 * 会话 runs / chat_history → 聊天时间线（与 HTTP 无关，供页面消费）
 */
import type { AssistantToolCallTag, SessionChatLine } from '@/types/chat'
import type { ModelMessage } from '@/types/os'

function parseToolCallsFromRow(
  row: Record<string, unknown>,
): AssistantToolCallTag[] | undefined {
  const tc = row.tool_calls
  if (!Array.isArray(tc) || tc.length === 0) return undefined
  const out: AssistantToolCallTag[] = []
  for (const item of tc) {
    if (item === null || typeof item !== 'object') continue
    const o = item as Record<string, unknown>
    const fn = o.function
    if (fn !== null && typeof fn === 'object') {
      const f = fn as Record<string, unknown>
      const name = typeof f.name === 'string' ? f.name.trim() : ''
      if (!name) continue
      let argStr: string | undefined
      if (typeof f.arguments === 'string') argStr = f.arguments
      else if (f.arguments != null && typeof f.arguments === 'object') {
        try {
          argStr = JSON.stringify(f.arguments)
        } catch {
          argStr = String(f.arguments)
        }
      }
      out.push({
        id: typeof o.id === 'string' ? o.id : undefined,
        name,
        arguments: argStr,
      })
    }
  }
  return out.length ? out : undefined
}

export function parseAgentRunResult(raw: unknown): {
  text: string
  sessionId?: string
  toolCalls?: AssistantToolCallTag[]
} {
  let sessionId: string | undefined

  const pickSession = (o: object) => {
    const r = o as Record<string, unknown>
    if (typeof r.session_id === 'string') sessionId = r.session_id
  }

  if (raw == null) return { text: '' }

  if (typeof raw === 'string') {
    try {
      const j = JSON.parse(raw) as unknown
      if (j !== null && typeof j === 'object') pickSession(j)
      return parseAgentRunResult(j)
    } catch {
      return { text: raw }
    }
  }

  if (typeof raw === 'object') {
    pickSession(raw)
    const o = raw as Record<string, unknown>
    const toolCallsFromRoot = parseToolCallsFromRow(o)
    if (typeof o.content === 'string') {
      return { text: o.content, sessionId, toolCalls: toolCallsFromRoot }
    }
    if (typeof o.content === 'number' || typeof o.content === 'boolean') {
      return { text: String(o.content), sessionId, toolCalls: toolCallsFromRoot }
    }
    if (o.content != null && typeof o.content === 'object') {
      try {
        return {
          text: JSON.stringify(o.content),
          sessionId,
          toolCalls: toolCallsFromRoot,
        }
      } catch {
        return {
          text: String(o.content),
          sessionId,
          toolCalls: toolCallsFromRoot,
        }
      }
    }
    if (Array.isArray(raw)) {
      const parts: string[] = []
      let toolCalls: AssistantToolCallTag[] | undefined
      for (const item of raw) {
        if (item !== null && typeof item === 'object') {
          pickSession(item)
          const row = item as Record<string, unknown>
          const tc = parseToolCallsFromRow(row)
          if (tc?.length) toolCalls = tc
          const c = row.content
          if (typeof c === 'string') parts.push(c)
        }
      }
      if (parts.length) return { text: parts.join(''), sessionId, toolCalls }
    }
  }

  try {
    const toolCalls =
      raw !== null && typeof raw === 'object' && !Array.isArray(raw)
        ? parseToolCallsFromRow(raw as Record<string, unknown>)
        : undefined
    return { text: JSON.stringify(raw), sessionId, toolCalls }
  } catch {
    return { text: String(raw), sessionId }
  }
}

export function mergeAssistantToolOutputs(
  lines: SessionChatLine[],
): SessionChatLine[] {
  const result: SessionChatLine[] = []
  let i = 0
  while (i < lines.length) {
    const cur = lines[i]
    if (cur.role === 'assistant' && cur.toolCalls?.length) {
      const toolOutputs: string[] = []
      let j = i + 1
      while (j < lines.length && lines[j].role === 'tool') {
        toolOutputs.push(lines[j].body)
        j++
      }
      result.push({
        ...cur,
        toolOutputs: toolOutputs.length ? toolOutputs : undefined,
      })
      i = j
      continue
    }
    result.push(cur)
    i++
  }
  return result
}

export function mergeConsecutiveAssistantMessages(
  lines: SessionChatLine[],
): SessionChatLine[] {
  const result: SessionChatLine[] = []
  for (const line of lines) {
    if (line.role !== 'assistant') {
      result.push(line)
      continue
    }
    const prev = result[result.length - 1]
    if (prev?.role === 'assistant') {
      const parts = [prev.body.trim(), line.body.trim()].filter((s) => s.length > 0)
      const toolCalls = [...(prev.toolCalls ?? []), ...(line.toolCalls ?? [])]
      const toolOutputs = [...(prev.toolOutputs ?? []), ...(line.toolOutputs ?? [])]
      const merged: SessionChatLine = {
        role: 'assistant',
        body: parts.join('\n\n'),
        toolCalls: toolCalls.length ? toolCalls : undefined,
        toolOutputs: toolOutputs.length ? toolOutputs : undefined,
      }
      result[result.length - 1] = merged
    } else {
      result.push({ ...line })
    }
  }
  return result
}

function sortRunsChronologically(runs: unknown[]): unknown[] {
  return [...runs].sort((a, b) => {
    const ta =
      a !== null && typeof a === 'object' && 'created_at' in a
        ? Number((a as Record<string, unknown>).created_at)
        : NaN
    const tb =
      b !== null && typeof b === 'object' && 'created_at' in b
        ? Number((b as Record<string, unknown>).created_at)
        : NaN
    const na = Number.isFinite(ta) ? ta : 0
    const nb = Number.isFinite(tb) ? tb : 0
    return na - nb
  })
}

function contentToText(value: unknown): string {
  if (typeof value === 'string') return value
  if (value == null) return ''
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function messageRowsToChatLines(rows: unknown[]): SessionChatLine[] {
  const out: SessionChatLine[] = []
  for (const m of rows) {
    if (m === null || typeof m !== 'object') continue
    const row = m as Record<string, unknown>
    const role = row.role
    const text = contentToText(row.content).trim()
    if (role === 'system') continue
    if (role === 'user') {
      if (!text) continue
      out.push({ role: 'user', body: text })
    } else if (role === 'assistant') {
      const toolCalls = parseToolCallsFromRow(row)
      if (!text && !toolCalls?.length) continue
      out.push({ role: 'assistant', body: text, toolCalls })
    } else if (role === 'tool') {
      if (!text) continue
      out.push({ role: 'tool', body: text })
    }
  }
  return out
}

function normalizeRunsArray(payload: unknown): unknown[] {
  if (Array.isArray(payload)) return payload
  if (payload !== null && typeof payload === 'object') {
    const d = (payload as Record<string, unknown>).data
    if (Array.isArray(d)) return d
  }
  return []
}

export function sessionRunsToChatMessages(runs: unknown): SessionChatLine[] {
  if (runs !== null && typeof runs === 'object' && !Array.isArray(runs)) {
    const root = runs as Record<string, unknown>
    const ch = root.chat_history
    if (Array.isArray(ch) && ch.length > 0) {
      /** GET session 的 `chat_history` 与 agent-ui {@link ModelMessage} 一致 */
      return mergeConsecutiveAssistantMessages(
        mergeAssistantToolOutputs(messageRowsToChatLines(ch as ModelMessage[])),
      )
    }
  }

  const list = normalizeRunsArray(runs)
  if (!list.length) return []
  const ordered = sortRunsChronologically(list)
  const out: SessionChatLine[] = []

  for (const run of ordered) {
    if (run === null || typeof run !== 'object') continue
    const r = run as Record<string, unknown>
    const rawMsgs = r.messages

    if (Array.isArray(rawMsgs) && rawMsgs.length > 0) {
      out.push(...messageRowsToChatLines(rawMsgs))
      continue
    }

    const input = contentToText(r.run_input).trim()
    const reply = contentToText(r.content).trim()
    if (input) out.push({ role: 'user', body: input })
    if (reply) out.push({ role: 'assistant', body: reply })
  }

  return mergeConsecutiveAssistantMessages(mergeAssistantToolOutputs(out))
}
