<script setup lang="ts">
import {
  IconDownload,
  IconLoader2,
  IconRefresh,
  IconSend,
  IconStar,
  IconTool,
  IconUser,
} from "@tabler/icons-vue"
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
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

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
/** Agent 逐字输出：取消时补全全文 */
let cancelAgentTypewriter: (() => void) | null = null

const draft = ref("")

const selectedAgent = computed(() =>
  agents.value.find((a) => a.id === selectedAgentId.value),
)

const messages = ref<ChatMessage[]>([])
/** 聊天记录区域原生滚动容器（不用 reka ScrollArea：:flex 链未截住高度时视口不会产生内部滚动，scrollTop 无效） */
const chatScrollViewportRef = ref<HTMLElement | null>(null)
/** 聊天记录底部锚点 */
const chatScrollEndRef = ref<HTMLElement | null>(null)

function applyChatScrollToBottom() {
  const vp = chatScrollViewportRef.value
  const end = chatScrollEndRef.value
  if (!vp || !end) return

  /** 只滚消息区域，不用 scrollIntoView（会带动外层，顶栏/会话条会跟着跑） */
  const align = () => {
    vp.scrollTop = vp.scrollHeight
    const vr = vp.getBoundingClientRect()
    const er = end.getBoundingClientRect()
    const gap = er.bottom - vr.bottom
    if (gap > 0.5) {
      const maxTop = Math.max(0, vp.scrollHeight - vp.clientHeight)
      vp.scrollTop = Math.min(vp.scrollTop + gap, maxTop)
    }
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
  () => chatScrollEndRef.value,
  (end) => {
    teardownChatColumnResizeObserver()
    const col = end?.parentElement
    if (!col) return
    chatColumnResizeRo = new ResizeObserver(() => {
      if (loadingHistory.value) return
      cancelAnimationFrame(chatColumnResizeRaf)
      chatColumnResizeRaf = requestAnimationFrame(() => {
        applyChatScrollToBottom()
      })
    })
    chatColumnResizeRo.observe(col)
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
    const { text: reply, sessionId: returnedSid, toolCalls } =
      parseAgentRunResult(raw)
    if (returnedSid) {
      sessionChoice.value = returnedSid
    }
    const content =
      reply || (!toolCalls?.length ? t("chat.emptyReply") : "")
    const createdAt = nowTs()
    messages.value.push(
      agentReplyToChatMessage("", toolCalls, createdAt),
    )
    const idx = messages.value.length - 1
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

function onDraftKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault()
    if (!draft.value.trim()) return
    void sendMessage()
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
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col overflow-hidden bg-background">
      <!-- 会话 / 模型：与全局顶栏一并固定在视口内，不参与外层滚动 -->
      <div
        class="z-10 flex shrink-0 flex-wrap items-center gap-2 border-b border-border bg-background/95 px-3 py-2.5 backdrop-blur-md md:px-5"
      >
        <Select
          v-model="sessionChoice"
          :disabled="loadingSessions || loadingHistory || !sessions.length"
        >
          <SelectTrigger
            class="h-10 min-w-0 flex-1 rounded-xl border-border bg-card text-sm shadow-sm md:max-w-[min(100%,22rem)]"
          >
            <SelectValue
              :placeholder="
                sessions.length
                  ? t('chat.selectSessionPlaceholder')
                  : t('chat.noSessionPlaceholder')
              "
            />
          </SelectTrigger>
          <SelectContent>
            <SelectItem
              v-for="s in sessions"
              :key="s.session_id"
              :value="s.session_id"
            >
              {{ s.session_name || s.session_id }}
            </SelectItem>
          </SelectContent>
        </Select>
        <Select v-model="selectedAgentId">
          <SelectTrigger
            class="h-10 min-w-0 flex-1 rounded-xl border-border bg-card text-sm shadow-sm md:max-w-[min(100%,20rem)]"
            :disabled="loadingAgents || !agents.length"
          >
            <SelectValue placeholder="Agent" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem
              v-for="a in agents"
              :key="a.id"
              :value="a.id"
            >
              {{ a.name || a.id }}
            </SelectItem>
          </SelectContent>
        </Select>
        <p
          v-if="selectedAgent?.model"
          class="hidden w-full text-xs text-muted-foreground md:block md:max-w-[min(100%,20rem)] md:flex-none"
        >
          {{ selectedAgent.model.model }} · {{ selectedAgent.model.provider }}
        </p>
        <Separator orientation="vertical" class="hidden h-8 md:block" />
        <div class="flex w-full items-center justify-end gap-1.5 sm:ml-auto sm:w-auto">
          <Button
            variant="outline"
            size="icon"
            class="size-10 rounded-xl border-border bg-card shadow-sm"
            :title="t('chat.refreshMeta')"
            :disabled="loadingAgents || loadingSessions"
            @click="void refreshChatMeta()"
          >
            <IconRefresh class="size-4 text-muted-foreground" />
          </Button>
        </div>
      </div>

      <!-- 消息：原生 overflow-y-auto，保证在 flex 布局下一定有可滚动高度 -->
      <div
        ref="chatScrollViewportRef"
        class="min-h-0 flex-1 basis-0 overflow-y-auto overscroll-y-contain px-3 pb-5 pt-5 md:px-6"
      >
        <div class="mx-auto flex max-w-3xl flex-col gap-5">
          <p
            v-if="loadingHistory"
            class="rounded-lg border border-dashed border-border bg-muted/40 px-4 py-6 text-center text-sm text-muted-foreground dark:bg-muted/30"
          >
            {{ t("chat.loadingHistory") }}
          </p>
          <div
            v-for="(msg, i) in messages"
            :key="`${msg.role}-${msg.created_at}-${i}`"
            class="flex gap-3"
            :class="[
              msg.role === 'tool' ? 'opacity-95' : '',
              msg.role === 'user' ? 'flex-row-reverse' : '',
            ]"
          >
            <template
              v-if="msg.role === 'agent' && msg.tool_calls?.length"
            >
              <div class="min-w-0 flex-1 space-y-2">
                <div
                  class="grid grid-cols-[2.25rem_minmax(0,1fr)] gap-x-3 gap-y-2"
                >
                  <div
                    class="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-xl border border-border bg-card shadow-sm"
                  >
                    <IconTool class="size-4 text-muted-foreground" />
                  </div>
                  <ChatToolCallsCard :tool-calls="msg.tool_calls" />
                  <template v-if="msg.content.trim()">
                    <div
                      class="flex size-9 shrink-0 items-center justify-center rounded-xl border border-border bg-card shadow-sm"
                    >
                      <IconStar class="size-4 text-amber-500" />
                    </div>
                    <div
                      class="min-w-0 rounded-xl border border-border bg-card px-4 py-3.5 text-[13px] leading-relaxed text-foreground shadow-sm"
                    >
                      <div
                        class="chat-md min-w-0 text-left [&_a]:break-all [&_img]:max-w-full [&_img]:h-auto"
                        v-html="renderChatMarkdown(msg.content)"
                      />
                    </div>
                  </template>
                </div>
              </div>
            </template>
            <template v-else>
              <div
                class="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-xl border border-border bg-card shadow-sm"
              >
                <IconUser
                  v-if="msg.role === 'user'"
                  class="size-4 text-sky-600 dark:text-sky-400"
                />
                <IconStar
                  v-else-if="msg.role === 'agent'"
                  class="size-4 text-amber-500"
                />
                <IconTool v-else class="size-4 text-muted-foreground" />
              </div>
              <div
                class="min-w-0 space-y-2"
                :class="msg.role === 'user' ? 'flex-1 text-right' : 'flex-1'"
              >
                <div
                  class="rounded-xl border px-4 py-3.5 text-[13px] leading-relaxed shadow-sm"
                  :class="
                    msg.role === 'user'
                      ? 'ml-auto inline-block min-w-0 max-w-[min(100%,36rem)] border-sky-200/80 bg-sky-50 text-foreground dark:border-sky-900/50 dark:bg-sky-950/40'
                      : msg.role === 'tool'
                        ? 'border-border bg-muted text-foreground dark:border-white/10 dark:bg-secondary/80'
                        : 'border-border bg-card text-foreground'
                  "
                >
                  <ChatToolOutputTags
                    v-if="msg.role === 'tool'"
                    :text="msg.content"
                  />
                  <template v-else-if="msg.role === 'agent'">
                    <div
                      v-if="msg.content.trim()"
                      class="chat-md min-w-0 text-left [&_a]:break-all [&_img]:max-w-full [&_img]:h-auto"
                      v-html="renderChatMarkdown(msg.content)"
                    />
                  </template>
                  <p
                    v-else
                    class="whitespace-pre-wrap break-all text-left text-pretty [overflow-wrap:anywhere]"
                  >
                    {{ msg.content }}
                  </p>
                </div>
              </div>
            </template>
          </div>
          <div
            v-if="sending"
            class="flex gap-3"
            aria-live="polite"
            aria-busy="true"
          >
            <div
              class="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-xl border border-border bg-card shadow-sm"
            >
              <IconStar class="size-4 text-amber-500" />
            </div>
            <div class="min-w-0 flex-1 space-y-2">
              <div
                class="inline-flex max-w-[min(100%,36rem)] items-center gap-2 rounded-xl border border-border bg-card px-4 py-3.5 text-[13px] text-muted-foreground shadow-sm"
              >
                <IconLoader2 class="size-4 shrink-0 animate-spin text-amber-500" aria-hidden="true" />
                <span>{{ t("chat.replying") }}</span>
              </div>
            </div>
          </div>
          <div
            ref="chatScrollEndRef"
            class="h-px w-full shrink-0 scroll-mt-0"
            aria-hidden="true"
          />
        </div>
      </div>

      <!-- 输入 -->
      <div
        class="sticky bottom-0 z-10 mt-auto border-t border-border bg-background/95 p-3 backdrop-blur-md md:p-4"
      >
        <div class="mx-auto max-w-3xl">
          <div
            class="rounded-xl border border-border bg-card p-1.5 shadow-lg shadow-foreground/5 dark:shadow-none"
          >
            <Textarea
              v-model="draft"
              :placeholder="t('chat.messagePlaceholder')"
              class="min-h-[80px] resize-none rounded-lg border-0 bg-transparent px-3 py-3 text-sm text-foreground placeholder:text-muted-foreground focus-visible:ring-0"
              @keydown="onDraftKeydown"
            />
            <div class="flex items-center justify-end gap-0.5 px-2 pb-1 pt-0.5">
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="size-9 text-muted-foreground"
                      :disabled="loadingHistory || !messages.length"
                      :aria-label="t('chat.downloadChatAria')"
                      @click="downloadCurrentChatMarkdown"
                    >
                      <IconDownload class="size-5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{{ t("chat.downloadChatTooltip") }}</TooltipContent>
                </Tooltip>
                <Button
                  type="button"
                  size="icon"
                  class="ml-1 size-11 rounded-full shadow-md"
                  :disabled="sending || loadingHistory || !draft.trim()"
                  :title="t('chat.send')"
                  @click="void sendMessage()"
                >
                  <IconSend class="size-5" />
                </Button>
            </div>
          </div>
        </div>
      </div>
  </div>
</template>
