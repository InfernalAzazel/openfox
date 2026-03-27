/**
 * 与 agno agent-ui 官方类型对齐
 * @see https://github.com/agno-agi/agent-ui/blob/main/src/types/os.ts
 */

export interface ToolCall {
  role: 'user' | 'tool' | 'system' | 'assistant'
  content: string | null
  tool_call_id: string
  tool_name: string
  tool_args: Record<string, string>
  tool_call_error: boolean
  metrics: {
    time: number
  }
  created_at: number
}

export interface ReasoningSteps {
  title: string
  action?: string
  result: string
  reasoning: string
  confidence?: number
  next_action?: string
}

export interface ReasoningStepProps {
  index: number
  stepTitle: string
}

export interface ReasoningProps {
  reasoning: ReasoningSteps[]
}

export type ToolCallProps = {
  tools: ToolCall
}

export interface MessageContext {
  query: string
  docs?: Array<Record<string, object>>
  time?: number
}

export interface ModelMessage {
  content: string | null
  context?: MessageContext[]
  created_at: number
  metrics?: {
    time: number
    prompt_tokens: number
    input_tokens: number
    completion_tokens: number
    output_tokens: number
  }
  name: string | null
  role: string
  tool_args?: unknown
  tool_call_id: string | null
  tool_calls: Array<{
    function: {
      arguments: string
      name: string
    }
    id: string
    type: string
  }> | null
}

export interface Model {
  name: string
  model: string
  provider: string
}

export interface Agent {
  agent_id: string
  name: string
  description: string
  model: Model
  storage?: boolean
}

export interface Team {
  team_id: string
  name: string
  description: string
  model: Model
  storage?: boolean
}

/** 与 agent-ui `RunEvent` 枚举字符串一致（本项目 tsconfig 使用 erasableSyntaxOnly，故用 const + 联合类型） */
export const RunEvent = {
  RunStarted: 'RunStarted',
  RunContent: 'RunContent',
  RunCompleted: 'RunCompleted',
  RunError: 'RunError',
  RunOutput: 'RunOutput',
  UpdatingMemory: 'UpdatingMemory',
  ToolCallStarted: 'ToolCallStarted',
  ToolCallCompleted: 'ToolCallCompleted',
  MemoryUpdateStarted: 'MemoryUpdateStarted',
  MemoryUpdateCompleted: 'MemoryUpdateCompleted',
  ReasoningStarted: 'ReasoningStarted',
  ReasoningStep: 'ReasoningStep',
  ReasoningCompleted: 'ReasoningCompleted',
  RunCancelled: 'RunCancelled',
  RunPaused: 'RunPaused',
  RunContinued: 'RunContinued',
  TeamRunStarted: 'TeamRunStarted',
  TeamRunContent: 'TeamRunContent',
  TeamRunCompleted: 'TeamRunCompleted',
  TeamRunError: 'TeamRunError',
  TeamRunCancelled: 'TeamRunCancelled',
  TeamToolCallStarted: 'TeamToolCallStarted',
  TeamToolCallCompleted: 'TeamToolCallCompleted',
  TeamReasoningStarted: 'TeamReasoningStarted',
  TeamReasoningStep: 'TeamReasoningStep',
  TeamReasoningCompleted: 'TeamReasoningCompleted',
  TeamMemoryUpdateStarted: 'TeamMemoryUpdateStarted',
  TeamMemoryUpdateCompleted: 'TeamMemoryUpdateCompleted',
} as const

export type RunEvent = (typeof RunEvent)[keyof typeof RunEvent]

export interface ResponseAudio {
  id?: string
  content?: string
  transcript?: string
  channels?: number
  sample_rate?: number
}

export interface NewRunResponse {
  status: 'RUNNING' | 'PAUSED' | 'CANCELLED'
}

export interface ImageData {
  revised_prompt: string
  url: string
}

export interface VideoData {
  id: number
  eta: number
  url: string
}

export interface AudioData {
  base64_audio?: string
  mime_type?: string
  url?: string
  id?: string
  content?: string
  channels?: number
  sample_rate?: number
}

export interface Reference {
  content: string
  meta_data: {
    chunk: number
    chunk_size: number
  }
  name: string
}

export interface ReferenceData {
  query: string
  references: Reference[]
  time?: number
}

export interface ReasoningMessage {
  role: 'user' | 'tool' | 'system' | 'assistant'
  content: string | null
  tool_call_id?: string
  tool_name?: string
  tool_args?: Record<string, string>
  tool_call_error?: boolean
  metrics?: {
    time: number
  }
  created_at?: number
}

/** 合并官方文件中重复声明的 AgentExtraData */
export interface AgentExtraData {
  reasoning_steps?: ReasoningSteps[]
  reasoning_messages?: ReasoningMessage[]
  references?: ReferenceData[]
}

export interface RunResponseContent {
  content?: string | object
  content_type: string
  context?: MessageContext[]
  event: RunEvent
  event_data?: object
  messages?: ModelMessage[]
  metrics?: object
  model?: string
  run_id?: string
  agent_id?: string
  session_id?: string
  tool?: ToolCall
  tools?: ToolCall[]
  created_at: number
  extra_data?: AgentExtraData
  images?: ImageData[]
  videos?: VideoData[]
  audio?: AudioData[]
  response_audio?: ResponseAudio
}

export interface RunResponse {
  content?: string | object
  content_type: string
  context?: MessageContext[]
  event: RunEvent
  event_data?: object
  messages?: ModelMessage[]
  metrics?: object
  model?: string
  run_id?: string
  agent_id?: string
  session_id?: string
  tool?: ToolCall
  tools?: ToolCall[]
  created_at: number
  extra_data?: AgentExtraData
  images?: ImageData[]
  videos?: VideoData[]
  audio?: AudioData[]
  response_audio?: ResponseAudio
}

export interface ChatMessage {
  role: 'user' | 'agent' | 'system' | 'tool'
  content: string
  streamingError?: boolean
  created_at: number
  tool_calls?: ToolCall[]
  extra_data?: {
    reasoning_steps?: ReasoningSteps[]
    reasoning_messages?: ReasoningMessage[]
    references?: ReferenceData[]
  }
  images?: ImageData[]
  videos?: VideoData[]
  audio?: AudioData[]
  response_audio?: ResponseAudio
}

/** 与 agent-ui 一致 */
export interface AgentDetails {
  id: string
  name?: string
  db_id?: string
  model?: Model
}

export interface TeamDetails {
  id: string
  name?: string
  db_id?: string
  model?: Model
}

export interface SessionEntry {
  session_id: string
  session_name: string
  created_at: number
  updated_at?: number
}

export interface Pagination {
  page: number
  limit: number
  total_pages: number
  total_count: number
}

/**
 * 官方写为 `extends SessionEntry`；实际列表 API 多为根级 `{ data, meta? }`。
 * 这里采用运行时常见形状，避免误要求根级含 session_id。
 */
export interface Sessions {
  data: SessionEntry[]
  meta?: Pagination
}

export interface ChatEntry {
  message: {
    role: 'user' | 'system' | 'tool' | 'assistant'
    content: string
    created_at: number
  }
  response: {
    content: string
    tools?: ToolCall[]
    extra_data?: {
      reasoning_steps?: ReasoningSteps[]
      reasoning_messages?: ReasoningMessage[]
      references?: ReferenceData[]
    }
    images?: ImageData[]
    videos?: VideoData[]
    audio?: AudioData[]
    response_audio?: {
      transcript?: string
    }
    created_at: number
  }
}

/** Agent OS `GET /metrics` / `POST /metrics/refresh` 日聚合（与 OpenAPI 字段对齐） */
export interface AgentOsTokenMetrics {
  input_tokens?: number
  output_tokens?: number
  total_tokens?: number
  audio_tokens?: number
  input_audio_tokens?: number
  output_audio_tokens?: number
  audio_total_tokens?: number
  audio_input_tokens?: number
  audio_output_tokens?: number
  cached_tokens?: number
  cache_read_tokens?: number
  cache_write_tokens?: number
  reasoning_tokens?: number
}

export interface AgentOsDayAggregatedMetrics {
  id?: string
  agent_runs_count?: number
  agent_sessions_count?: number
  team_runs_count?: number
  team_sessions_count?: number
  workflow_runs_count?: number
  workflow_sessions_count?: number
  users_count?: number
  token_metrics?: AgentOsTokenMetrics
  model_metrics?: { model_id?: string; model_provider?: string; count?: number }[]
  date?: string
  created_at?: string
  updated_at?: string
}

export interface AgentOsMetricsResponse {
  metrics: AgentOsDayAggregatedMetrics[]
}
