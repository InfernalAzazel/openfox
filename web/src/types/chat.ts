/** 聊天 UI 用的结构与 OpenAI 形态 tool_calls 解析结果 */

export type AssistantToolCallTag = {
  id?: string
  name: string
  arguments?: string
}

export type SessionChatLine =
  | { role: 'user'; body: string }
  | {
      role: 'assistant'
      body: string
      toolCalls?: AssistantToolCallTag[]
      toolOutputs?: string[]
    }
  | { role: 'tool'; body: string }
