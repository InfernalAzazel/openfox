<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue"
import { useI18n } from "vue-i18n"
import {
  getAgentsAPI,
  getAllSessionsAPI,
  getSessionAPI,
  runAgentAPI,
} from "@/api/os"
import {
  parseAgentRunResult,
  sessionRunsToChatMessages,
} from "@/composables/agentSessionChat"
import {
  agentReplyToChatMessage,
  sessionLinesToChatMessages,
} from "@/composables/chatViewModel"
import { getAgentOsBaseUrl } from "@/composables/request"
import { useAppState } from "@/composables/store"
import { runTypewriter } from "@/composables/typewriterReply"
import ChatToolCallsCard from "@/components/ChatToolCallsCard.vue"
import ChatToolOutputTags from "@/components/ChatToolOutputTags.vue"
import { formatAgentRunErrorMessage } from "@/lib/agentRunErrors"
import {
  chatMessagesToMarkdown,
  safeFilenameSegment,
  triggerDownloadMarkdown,
} from "@/lib/exportChatMarkdown"
import { renderChatMarkdown } from "@/lib/markdown"
import type { AgentDetails, ChatMessage, SessionEntry } from "@/types/os"

const { t } = useI18n()
const app = useAppState()

const agents = ref<AgentDetails[]>([])
const selectedAgentId = ref("")
const sessions = ref<SessionEntry[]>([])
/** 当前选中的会话 id；空字符串表示未选择（无会话或用户未选），此时发消息由服务端创建会话 */
const sessionChoice = ref<string>("")
const loadingAgents = ref(false)
const loadingSessions = ref(false)
const loadingHistory = ref(false)
const sending = ref(false)
/** 切换会话时的并发请求序号，避免慢请求覆盖新会话内容 */
let sessionHistoryRequestId = 0
/**
 * 从「无会话」首次绑定 run 返回的 session_id 时跳过一次历史拉取，避免清空后用尚未含 tool_calls 的 GET 覆盖本地消息。
 */
let skipSessionHistoryLoadOnce = false
/** Agent 逐字输出：取消时补全全文 */
let cancelAgentTypewriter: (() => void) | null = null

const draft = ref("")

const selectedAgent = computed(() =>
  agents.value.find((a) => a.id === selectedAgentId.value),
)

const sessionSelectItems = computed(() =>
  sessions.value.map((s) => ({
    value: s.session_id,
    label: s.session_name || s.session_id,
  })),
)

const agentSelectItems = computed(() =>
  agents.value.map((a) => ({
    value: a.id,
    label: a.name || a.id,
  })),
)

/** 供 Nuxt UI UChatMessages 使用（需 id / role / parts；与 @ai-sdk/vue 的 UIMessage 形状对齐） */
interface UiChatRow {
  id: string
  role: "user" | "assistant"
  parts: { type: "text"; text?: string }[]
  metadata: { raw: ChatMessage; index: number }
  variant?: string
  ui?: Record<string, string>
}

const messages = ref<ChatMessage[]>([])

const uiMessages = computed<UiChatRow[]>(() =>
  messages.value.map((raw, index) => {
    const id = `m-${raw.role}-${raw.created_at}-${index}`
    const base: UiChatRow = {
      id,
      role: raw.role === "user" ? "user" : "assistant",
      parts: [],
      metadata: { raw, index },
    }
    if (raw.role === "agent" && raw.tool_calls?.length) {
      return {
        ...base,
        variant: "naked",
        ui: {
          root: "w-full max-w-none",
          container: "max-w-none w-full",
          leading: "!hidden",
        },
      }
    }
    if (raw.role === "tool") {
      return {
        ...base,
        ui: { root: "opacity-95" },
      }
    }
    return base
  }),
)

/** UChatMessages / UChatPromptSubmit：与 AI SDK 的 chat.status 命名一致 */
const chatMessagesStatus = computed(() =>
  sending.value ? "submitted" : "ready",
)

/** 聊天记录区域原生滚动容器（:flex 链需 min-h-0 + overflow 才有可滚动高度） */
const chatScrollViewportRef = ref<HTMLElement | null>(null)

function applyChatScrollToBottom() {
  const vp = chatScrollViewportRef.value
  if (!vp) return
  const align = () => {
    vp.scrollTop = vp.scrollHeight
  }
  align()
  requestAnimationFrame(() => {
    align()
    requestAnimationFrame(align)
  })
}

function scrollChatToBottom() {
  void nextTick(() => {
    requestAnimationFrame(() => {
      requestAnimationFrame(applyChatScrollToBottom)
    })
  })
}

/** 历史 / Markdown 渲染后内容高度会继续变化，ResizeObserver 再对齐一次底部 */
let chatColumnResizeRo: ResizeObserver | null = null
let chatColumnResizeRaf = 0

function teardownChatColumnResizeObserver() {
  if (chatColumnResizeRaf) {
    cancelAnimationFrame(chatColumnResizeRaf)
    chatColumnResizeRaf = 0
  }
  chatColumnResizeRo?.disconnect()
  chatColumnResizeRo = null
}

watch(
  () => chatScrollViewportRef.value,
  (vp) => {
    teardownChatColumnResizeObserver()
    if (!vp) return
    chatColumnResizeRo = new ResizeObserver(() => {
      if (loadingHistory.value) return
      cancelAnimationFrame(chatColumnResizeRaf)
      chatColumnResizeRaf = requestAnimationFrame(() => {
        applyChatScrollToBottom()
      })
    })
    chatColumnResizeRo.observe(vp)
  },
  { flush: "post", immediate: true },
)

onUnmounted(() => {
  teardownChatColumnResizeObserver()
  cancelAgentTypewriter?.()
  cancelAgentTypewriter = null
})

function nowTs() {
  return Date.now()
}

function authHeaders() {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim()
  return { base, token }
}

async function refreshAgents() {
  const { base, token } = authHeaders()
  if (!base || !token) return
  loadingAgents.value = true
  try {
    agents.value = await getAgentsAPI(base, token)
    if (!selectedAgentId.value && agents.value[0]) {
      selectedAgentId.value = agents.value[0].id
    }
  } finally {
    loadingAgents.value = false
  }
}

function sortSessionsByRecent(list: SessionEntry[]): SessionEntry[] {
  return [...list].sort((a, b) => {
    const tb = (b.updated_at ?? b.created_at) ?? 0
    const ta = (a.updated_at ?? a.created_at) ?? 0
    return tb - ta
  })
}

async function refreshSessions() {
  const { base, token } = authHeaders()
  const agentId = selectedAgentId.value
  if (!base || !token || !agentId) {
    sessions.value = []
    sessionChoice.value = ""
    return
  }
  const dbId = selectedAgent.value?.db_id ?? ""
  loadingSessions.value = true
  try {
    const res = await getAllSessionsAPI(base, "agent", agentId, dbId, token)
    if (!res.ok) {
      sessions.value = []
      sessionChoice.value = ""
      return
    }
    const sorted = sortSessionsByRecent(res.data)
    sessions.value = sorted
    const ids = new Set(sorted.map((s) => s.session_id))
    const cur = sessionChoice.value
    if (cur && ids.has(cur)) {
      return
    }
    if (sorted.length > 0) {
      sessionChoice.value = sorted[0].session_id
    } else {
      sessionChoice.value = ""
    }
  } finally {
    loadingSessions.value = false
  }
}

async function sendMessage() {
  const text = draft.value.trim()
  if (!text || sending.value || loadingHistory.value) return
  cancelAgentTypewriter?.()
  cancelAgentTypewriter = null
  const { base, token } = authHeaders()
  const agentId = selectedAgentId.value
  if (!base || !token) {
    messages.value.push({
      role: "agent",
      content: t("chat.errNeedLogin"),
      created_at: nowTs(),
    })
    return
  }
  if (!agentId) {
    messages.value.push({
      role: "agent",
      content: t("chat.errNoAgent"),
      created_at: nowTs(),
    })
    return
  }

  messages.value.push({
    role: "user",
    content: text,
    created_at: nowTs(),
  })
  draft.value = ""
  sending.value = true
  try {
    const sid = sessionChoice.value.trim() || undefined
    const raw = await runAgentAPI(
      base,
      agentId,
      {
        message: text,
        stream: false,
        sessionId: sid,
      },
      token,
    )
    const { text: reply, sessionId: returnedSid, toolCalls, toolOutputs } =
      parseAgentRunResult(raw)
    const content =
      reply || (!toolCalls?.length ? t("chat.emptyReply") : "")
    const createdAt = nowTs()
    /** 必须先插入带 tool_calls 的消息，再更新 sessionChoice，否则 watcher 会清空列表并用不完整的历史覆盖 */
    messages.value.push(
      agentReplyToChatMessage("", toolCalls, createdAt, toolOutputs),
    )
    const idx = messages.value.length - 1
    if (returnedSid) {
      if (!sessionChoice.value.trim()) {
        skipSessionHistoryLoadOnce = true
      }
      sessionChoice.value = returnedSid
    }
    if (!content) {
      await refreshSessions()
    } else {
      cancelAgentTypewriter = runTypewriter(
        content,
        (soFar) => {
          const row = messages.value[idx]
          if (row?.role === "agent") row.content = soFar
          scrollChatToBottom()
        },
        {
          msPerChar: 20,
          onComplete: () => {
            cancelAgentTypewriter = null
            void refreshSessions()
          },
        },
      )
    }
  } catch (e) {
    const raw = e instanceof Error ? e.message : String(e)
    messages.value.push({
      role: "agent",
      content: t("chat.errRequestFailed", {
        message: formatAgentRunErrorMessage(raw),
      }),
      created_at: nowTs(),
    })
  } finally {
    sending.value = false
  }
}

onMounted(() => {
  void refreshAgents()
})

watch(
  () => [selectedAgentId.value, app.value.access_token],
  () => {
    void refreshSessions()
  },
)

watch(
  () => [messages.value.length, loadingHistory.value] as const,
  ([, loading]) => {
    if (loading) return
    scrollChatToBottom()
  },
  { flush: "post" },
)

/** 历史加载结束必滚到底（与 length watch 互补：整页刷新等场景更稳） */
watch(
  loadingHistory,
  (loading) => {
    if (!loading) scrollChatToBottom()
  },
  { flush: "post" },
)

watch(
  sending,
  (v) => {
    if (v) scrollChatToBottom()
  },
  { flush: "post" },
)

watch(sessionChoice, async (sid) => {
  if (!sid.trim()) {
    cancelAgentTypewriter?.()
    cancelAgentTypewriter = null
    messages.value = []
    return
  }

  if (skipSessionHistoryLoadOnce) {
    skipSessionHistoryLoadOnce = false
    void refreshSessions()
    return
  }

  cancelAgentTypewriter?.()
  cancelAgentTypewriter = null
  messages.value = []
  const req = ++sessionHistoryRequestId
  const { base, token } = authHeaders()
  const agentId = selectedAgentId.value
  if (!base || !token || !agentId) {
    return
  }

  loadingHistory.value = true
  try {
    const dbId = selectedAgent.value?.db_id ?? ""
    const raw = await getSessionAPI(base, "agent", sid, dbId || undefined, token)
    if (req !== sessionHistoryRequestId) return
    messages.value = sessionLinesToChatMessages(
      sessionRunsToChatMessages(raw),
    )
  } catch (e) {
    if (req !== sessionHistoryRequestId) return
    messages.value = [
      {
        role: "agent",
        content: t("chat.errLoadHistory", {
          message: e instanceof Error ? e.message : String(e),
        }),
        created_at: nowTs(),
      },
    ]
  } finally {
    if (req === sessionHistoryRequestId) loadingHistory.value = false
  }
})

async function refreshChatMeta() {
  await refreshAgents()
  await refreshSessions()
  scrollChatToBottom()
}

function downloadCurrentChatMarkdown() {
  if (!messages.value.length || loadingHistory.value) return
  const sid = sessionChoice.value.trim()
  const session = sessions.value.find((s) => s.session_id === sid)
  const label = session?.session_name?.trim() || sid || t("chat.noSession")
  const md = chatMessagesToMarkdown(messages.value, {
    sessionId: sid || undefined,
    agentLabel:
      selectedAgent.value?.name?.trim() || selectedAgentId.value || undefined,
  })
  const seg = safeFilenameSegment(label)
  const stamp = new Date().toISOString().slice(0, 19).replace(/:/g, "-")
  triggerDownloadMarkdown(`openfox-${seg}-${stamp}.md`, md)
}

function onChatPromptSubmit() {
  void sendMessage()
}

function onChatPromptKeydown(event: KeyboardEvent) {
  if (event.isComposing) return
  if (event.key !== "Enter" || event.shiftKey) return
  // UChatPrompt 默认 Enter 提交；这里仅阻断提交事件传播，保留 textarea 的换行默认行为
  event.stopPropagation()
}

function onChatPromptStop() {
  cancelAgentTypewriter?.()
  cancelAgentTypewriter = null
}

function isAgentToolCallsRow(row: UiChatRow) {
  const r = row.metadata.raw
  return r.role === "agent" && !!r.tool_calls?.length
}
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col overflow-hidden bg-background">
      <!-- 会话 / 模型：与全局顶栏一并固定在视口内，不参与外层滚动 -->
      <div
        class="z-10 flex shrink-0 flex-wrap items-center gap-2 border-b border-border bg-background/95 px-3 py-1.5 backdrop-blur-md md:px-5"
      >
        <USelect
          v-model="sessionChoice"
          :items="sessionSelectItems"
          :placeholder="
            sessions.length
              ? t('chat.selectSessionPlaceholder')
              : t('chat.noSessionPlaceholder')
          "
          :disabled="loadingSessions || loadingHistory || !sessions.length"
          :loading="loadingSessions"
          size="md"
          class="h-10 min-w-0 flex-1 md:max-w-[min(100%,22rem)]"
          :ui="{ base: 'rounded-xl shadow-sm' }"
        />
        <USelect
          v-model="selectedAgentId"
          :items="agentSelectItems"
          placeholder="Agent"
          :disabled="loadingAgents || !agents.length"
          :loading="loadingAgents"
          size="md"
          class="h-10 min-w-0 flex-1 md:max-w-[min(100%,20rem)]"
          :ui="{ base: 'rounded-xl shadow-sm' }"
        />
        <p
          v-if="selectedAgent?.model"
          class="hidden w-full text-xs text-muted-foreground md:block md:max-w-[min(100%,20rem)] md:flex-none"
        >
          {{ selectedAgent.model.model }} · {{ selectedAgent.model.provider }}
        </p>
        <USeparator orientation="vertical" class="hidden h-8 md:block" />
        <div class="flex w-full items-center justify-end gap-1.5 sm:ml-auto sm:w-auto">
          <UButton
            variant="outline"
            color="neutral"
            square
            size="sm"
            icon="i-lucide-refresh-cw"
            :title="t('chat.refreshMeta')"
            :disabled="loadingAgents || loadingSessions"
            @click="void refreshChatMeta()"
          />
        </div>
      </div>

      <div
        ref="chatScrollViewportRef"
        class="min-h-0 flex-1 basis-0 overflow-y-auto overscroll-y-contain px-3 pb-5 pt-3 md:px-6"
      >
        <div class="mx-auto flex max-w-3xl flex-col gap-5">
          <UAlert
            v-if="loadingHistory"
            color="neutral"
            variant="subtle"
            class="justify-center text-center"
            :description="t('chat.loadingHistory')"
          />
          <UChatMessages
            :messages="uiMessages"
            :status="chatMessagesStatus"
            :should-auto-scroll="false"
            should-scroll-to-bottom
            class="min-h-0"
            :user="{ side: 'right', variant: 'naked' }"
            :assistant="{ side: 'left', variant: 'naked' }"
          >
            <template #leading="{ message }">
              <template v-if="!isAgentToolCallsRow(message)">
                <div
                  v-if="message.metadata.raw.role === 'user'"
                  class="flex size-9 shrink-0 items-center justify-center self-start rounded-xl border border-default bg-elevated shadow-sm"
                >
                  <UIcon
                    name="i-lucide-user"
                    class="size-4 text-sky-600 dark:text-sky-400"
                  />
                </div>
                <UIcon
                  v-else-if="message.metadata.raw.role === 'agent'"
                  name="i-lucide-star"
                  class="size-4 text-amber-500"
                />
                <UIcon
                  v-else
                  name="i-lucide-wrench"
                  class="size-4 text-muted-foreground"
                />
              </template>
            </template>
            <template #content="{ message }">
              <template v-if="isAgentToolCallsRow(message)">
                <div class="min-w-0 flex-1 space-y-2">
                  <div
                    class="grid grid-cols-[2.25rem_minmax(0,1fr)] gap-x-3 gap-y-2"
                  >
                    <div
                      class="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-xl border border-border bg-card shadow-sm"
                    >
                      <UIcon name="i-lucide-wrench" class="size-4 text-muted-foreground" />
                    </div>
                    <ChatToolCallsCard
                      :tool-calls="message.metadata.raw.tool_calls!"
                    />
                    <template v-if="message.metadata.raw.content.trim()">
                      <div
                        class="flex size-9 shrink-0 items-center justify-center rounded-xl border border-border bg-card shadow-sm"
                      >
                        <UIcon name="i-lucide-star" class="size-4 text-amber-500" />
                      </div>
                      <div
                        class="min-w-0 rounded-xl border border-border bg-card px-4 py-3.5 text-[13px] leading-relaxed text-foreground shadow-sm"
                      >
                        <div
                          class="chat-md min-w-0 text-left [&_a]:break-all [&_img]:max-w-full [&_img]:h-auto"
                          v-html="renderChatMarkdown(message.metadata.raw.content)"
                        />
                      </div>
                    </template>
                  </div>
                </div>
              </template>
              <template v-else>
                <div
                  class="rounded-xl border px-4 py-3.5 text-[13px] leading-relaxed shadow-sm"
                  :class="
                    message.metadata.raw.role === 'user'
                      ? 'ml-auto inline-block min-w-0 max-w-[min(100%,36rem)] border-sky-200/80 bg-sky-50 text-foreground dark:border-sky-900/50 dark:bg-sky-950/40'
                      : message.metadata.raw.role === 'tool'
                        ? 'border-border bg-muted text-foreground dark:border-white/10 dark:bg-secondary/80'
                        : 'border-border bg-card text-foreground'
                  "
                >
                  <ChatToolOutputTags
                    v-if="message.metadata.raw.role === 'tool'"
                    :text="message.metadata.raw.content"
                  />
                  <template v-else-if="message.metadata.raw.role === 'agent'">
                    <div
                      v-if="message.metadata.raw.content.trim()"
                      class="chat-md min-w-0 text-left [&_a]:break-all [&_img]:max-w-full [&_img]:h-auto"
                      v-html="renderChatMarkdown(message.metadata.raw.content)"
                    />
                  </template>
                  <p
                    v-else
                    class="whitespace-pre-wrap break-all text-left text-pretty wrap-anywhere"
                  >
                    {{ message.metadata.raw.content }}
                  </p>
                </div>
              </template>
            </template>
            <template #indicator>
              <div
                class="inline-flex max-w-[min(100%,36rem)] items-center gap-2 rounded-xl border border-border bg-card px-4 py-3.5 text-[13px] text-muted-foreground shadow-sm"
                aria-live="polite"
                aria-busy="true"
              >
                <UIcon name="i-lucide-loader-2" class="size-4 shrink-0 animate-spin text-amber-500" aria-hidden="true" />
                <span>{{ t("chat.replying") }}</span>
              </div>
            </template>
          </UChatMessages>
        </div>
      </div>

      <!-- 输入：UChatPrompt 默认插槽挂 UChatPromptSubmit；#footer 仅放辅助操作（与官方文档一致） -->
      <div
        class="sticky bottom-0 z-10 mt-auto border-t border-border bg-background/95 p-3 backdrop-blur-md md:p-4"
      >
        <div class="mx-auto max-w-3xl">
          <UChatPrompt
            v-model="draft"
            :placeholder="t('chat.messagePlaceholder')"
            :disabled="loadingHistory"
            :rows="3"
            :maxrows="12"
            variant="outline"
            :autofocus="false"
            class="rounded-xl shadow-lg shadow-foreground/5 dark:shadow-none"
            @submit="onChatPromptSubmit"
            @keydown.capture="onChatPromptKeydown"
          >
            <!-- 默认插槽 → 内部 UTextarea，用于右下角提交（见 https://ui.nuxt.com/docs/components/chat-prompt ） -->
            <UChatPromptSubmit
              :status="chatMessagesStatus"
              icon="i-lucide-arrow-up"
              color="primary"
              square
              class="shrink-0 shadow-md"
              :disabled="
                loadingHistory ||
                (chatMessagesStatus === 'ready' && !draft.trim())
              "
              :title="t('chat.send')"
              @stop="onChatPromptStop"
            />
            <template #footer>
              <UTooltip :text="t('chat.downloadChatTooltip')">
                <UButton
                  variant="ghost"
                  color="neutral"
                  class="size-9 text-muted-foreground"
                  :disabled="loadingHistory || !messages.length"
                  :aria-label="t('chat.downloadChatAria')"
                  type="button"
                  @click="downloadCurrentChatMarkdown"
                >
                  <UIcon name="i-lucide-download" class="size-5" />
                </UButton>
              </UTooltip>
            </template>
          </UChatPrompt>
        </div>
      </div>
  </div>
</template>
