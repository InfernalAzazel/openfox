<script setup lang="ts">
import type { TableColumn } from "@nuxt/ui"
import type { SortingState } from "@tanstack/vue-table"
import { h, computed, onMounted, ref, resolveComponent, watch } from "vue"
import { useI18n } from "vue-i18n"
import {
  deleteSessionAPI,
  getAgentsAPI,
  getAllSessionsAPI,
} from "@/api/os"
import { getAgentOsBaseUrl } from "@/composables/request"
import { useAppState } from "@/composables/store"
import type { AgentDetails, SessionEntry } from "@/types/os"

const { t, locale } = useI18n()
const app = useAppState()

const UCheckbox = resolveComponent("UCheckbox")
const UButton = resolveComponent("UButton")

const agents = ref<AgentDetails[]>([])
const selectedAgentId = ref("")
const sessions = ref<SessionEntry[]>([])
const loadingAgents = ref(false)
const loadingSessions = ref(false)
/** 会话列表请求失败时展示在表格上方（与调度页红字风格一致） */
const sessionsRequestError = ref<string | null>(null)
const deleting = ref(false)
const deleteConfirmOpen = ref(false)

/** 表排序：默认更新时间新→旧，与原先「从新到旧」一致 */
const sorting = ref<SortingState>([{ id: "updated_at", desc: true }])

/** 行选择（key 为 `get-row-id` 返回的会话 id） */
const rowSelection = ref<Record<string, boolean>>({})

const selectedAgent = computed(() =>
  agents.value.find((a) => a.id === selectedAgentId.value),
)

/** 会话列表对应表名（与 Agno 约定一致） */
const sessionsTableName = "agno_sessions"

const sessionsHeaderMeta = computed(() => {
  const fullId = selectedAgent.value?.db_id?.trim() || ""
  return {
    fullId: fullId || "—",
    table: sessionsTableName,
  }
})

/** 过长时前 28 字符 + `...`，完整值见 title */
const sessionsDbIdEllipsis = computed(() => {
  const id = sessionsHeaderMeta.value.fullId
  if (id === "—") {
    return id
  }
  const max = 28
  if (id.length <= max) {
    return id
  }
  return `${id.slice(0, max)}...`
})

const hasOsAuth = computed(() => {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim()
  return !!(base && token)
})

const selectedIds = computed(() =>
  Object.keys(rowSelection.value).filter((k) => rowSelection.value[k]),
)

const selectedCount = computed(() => selectedIds.value.length)

function authHeaders() {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim()
  return { base, token }
}

function normalizeMs(ts: number): number {
  return ts < 1_000_000_000_000 ? ts * 1000 : ts
}

/** 与截图一致：26 Mar 2026, 06:49 */
function formatUpdatedAt(ts: number | undefined): string {
  if (ts == null || Number.isNaN(ts)) return "—"
  try {
    const d = new Date(normalizeMs(ts))
    const loc = locale.value === "zh-CN" ? "zh-CN" : "en-GB"
    return new Intl.DateTimeFormat(loc, {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).format(d)
  } catch {
    return "—"
  }
}

function displayName(s: SessionEntry): string {
  const n = s.session_name?.trim()
  return n || String(s.session_id ?? "")
}

/** 统一成字符串，避免接口返回数字 id 时 includes 全选与行勾选不一致 */
function sid(s: SessionEntry): string {
  return String(s.session_id ?? "").trim()
}

function pruneRowSelectionToAlive(alive: Set<string>) {
  const next = { ...rowSelection.value }
  for (const k of Object.keys(next)) {
    if (!alive.has(k)) delete next[k]
  }
  rowSelection.value = next
}

function clearSelection() {
  rowSelection.value = {}
  deleteConfirmOpen.value = false
}

function openDeleteConfirm() {
  if (!selectedIds.value.length || deleting.value) return
  deleteConfirmOpen.value = true
}

async function confirmDeleteSessions() {
  if (!selectedIds.value.length || deleting.value) return
  const { base, token } = authHeaders()
  const dbId = selectedAgent.value?.db_id ?? ""
  if (!base || !token) return
  deleting.value = true
  const ids = [...selectedIds.value]
  try {
    for (const sessionId of ids) {
      const res = await deleteSessionAPI(base, dbId, sessionId, token)
      if (!res.ok) {
        const t = await res.text().catch(() => "")
        console.warn("delete session failed", sessionId, res.status, t)
      }
    }
    rowSelection.value = {}
    deleteConfirmOpen.value = false
    await refreshSessions()
  } finally {
    deleting.value = false
  }
}

async function refreshAgents() {
  const { base, token } = authHeaders()
  if (!base || !token) return
  loadingAgents.value = true
  try {
    agents.value = await getAgentsAPI(base, token)
    if (agents.value.length === 0) {
      selectedAgentId.value = ""
    } else if (
      !selectedAgentId.value
      || !agents.value.some((a) => a.id === selectedAgentId.value)
    ) {
      selectedAgentId.value = agents.value[0]!.id
    }
  } finally {
    loadingAgents.value = false
  }
}

async function refreshSessions() {
  const { base, token } = authHeaders()
  const agentId = selectedAgentId.value
  if (!base || !token || !agentId) {
    sessions.value = []
    sessionsRequestError.value = null
    rowSelection.value = {}
    return
  }
  const dbId = selectedAgent.value?.db_id ?? ""
  loadingSessions.value = true
  sessionsRequestError.value = null
  try {
    const res = await getAllSessionsAPI(base, "agent", agentId, dbId, token)
    if (!res.ok) {
      sessions.value = []
      rowSelection.value = {}
      sessionsRequestError.value = t("sessions.requestFailed", {
        message: res.message,
      })
      return
    }
    const list = res.data
    sessions.value = list
    const alive = new Set(list.map((s) => sid(s)).filter(Boolean))
    pruneRowSelectionToAlive(alive)
  } finally {
    loadingSessions.value = false
  }
}

async function refreshAll() {
  await refreshAgents()
  await refreshSessions()
}

const columns = computed<TableColumn<SessionEntry>[]>(() => [
  {
    id: "select",
    meta: {
      class: {
        th: "w-10",
        td: "w-10",
      },
    },
    header: ({ table }) =>
      h(UCheckbox, {
        "modelValue": table.getIsSomePageRowsSelected()
          ? "indeterminate"
          : table.getIsAllPageRowsSelected(),
        "onUpdate:modelValue": (value: boolean | "indeterminate") =>
          table.toggleAllPageRowsSelected(!!value),
        "aria-label": t("sessions.selectAll"),
      }),
    cell: ({ row }) =>
      h(UCheckbox, {
        "modelValue": row.getIsSelected(),
        "onUpdate:modelValue": (value: boolean | "indeterminate") =>
          row.toggleSelected(!!value),
        "aria-label": t("sessions.selectRow", {
          name: displayName(row.original),
        }),
      }),
    enableSorting: false,
    enableHiding: false,
  },
  {
    accessorKey: "session_name",
    header: t("sessions.colSessionName"),
    meta: {
      class: {
        th: "min-w-0 w-[55%]",
        td: "max-w-0 min-w-0",
      },
    },
    cell: ({ row }) => {
      const name = displayName(row.original)
      return h(
        "span",
        {
          class:
            "block min-w-0 truncate text-sm font-normal text-foreground",
          title: name,
        },
        name,
      )
    },
  },
  {
    id: "updated_at",
    accessorFn: (row) => {
      const raw = row.updated_at ?? row.created_at
      return raw == null ? 0 : normalizeMs(raw)
    },
    header: ({ column }) => {
      const isSorted = column.getIsSorted()
      return h("div", { class: "flex justify-end" }, [
        h(UButton, {
          color: "neutral",
          variant: "ghost",
          size: "sm",
          label: t("sessions.colUpdatedAt"),
          icon: isSorted
            ? (isSorted === "asc"
                ? "i-lucide-arrow-up-narrow-wide"
                : "i-lucide-arrow-down-wide-narrow")
            : "i-lucide-arrow-up-down",
          class: "-mx-2.5 h-8 text-sm font-medium",
          onClick: () =>
            column.toggleSorting(column.getIsSorted() === "asc"),
        }),
      ])
    },
    cell: ({ row }) =>
      formatUpdatedAt(row.original.updated_at ?? row.original.created_at),
    meta: {
      class: {
        th: "text-right",
        td: "text-right text-sm tabular-nums text-muted-foreground",
      },
    },
  },
])

onMounted(() => {
  void refreshAll()
})

watch(
  () => [selectedAgentId.value, app.value.access_token] as const,
  () => {
    rowSelection.value = {}
    deleteConfirmOpen.value = false
    void refreshSessions()
  },
)

watch(selectedCount, (n) => {
  if (n === 0) deleteConfirmOpen.value = false
})

/** 紧凑表格：减轻默认 th/td 的 py-3.5 + p-4，并隐藏 thead 下多余分隔行，避免「条数」与表头之间大块留白 */
const sessionsTableUi = {
  root: "overflow-x-auto",
  base: "min-w-full table-fixed",
  thead: "bg-elevated/40",
  /** 每个 th 底边形成表头与表体分隔（隐藏了组件内 separator 行后需自行画线） */
  th: "border-b border-default py-2 px-3 text-sm font-medium text-muted-foreground",
  tbody: "divide-y divide-default",
  /** 斑马线：奇偶行底色交替；选中行略加重 */
  tr: "odd:bg-default even:bg-elevated/30 data-[selected=true]:bg-primary/10 hover:bg-elevated/45 dark:even:bg-white/[0.06]",
  td: "py-2 px-3 text-sm align-middle",
  separator: "hidden",
  empty: "py-8 text-sm text-muted-foreground",
  loading: "py-8 text-sm",
}

</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col overflow-auto bg-background">
    <div class="w-full space-y-4 p-4 text-foreground md:p-6">
      <div class="flex w-full flex-wrap items-end gap-x-4 gap-y-3">
        <div
          class="inline-grid min-w-0 max-w-full grid-cols-[auto_auto] grid-rows-[auto_auto] gap-x-3 gap-y-0.5 sm:max-w-[min(100%,36rem)] sm:gap-x-4"
        >
          <span
            class="col-start-1 row-start-1 text-xs leading-none text-muted-foreground"
          >
            {{ t("common.metaDatabase") }}
          </span>
          <span
            class="col-start-2 row-start-1 text-xs leading-none text-muted-foreground"
          >
            {{ t("common.metaTable") }}
          </span>
          <span
            class="col-start-1 row-start-2 min-w-0 max-w-[min(100%,20rem)] font-mono text-sm leading-snug font-medium whitespace-nowrap sm:max-w-[24rem]"
            :title="sessionsHeaderMeta.fullId !== '—' ? sessionsHeaderMeta.fullId : undefined"
          >
            {{ sessionsDbIdEllipsis }}
          </span>
          <span
            class="col-start-2 row-start-2 font-mono text-sm leading-snug font-medium whitespace-nowrap"
          >
            {{ sessionsHeaderMeta.table }}
          </span>
        </div>
      </div>

      <div class="flex flex-col gap-3">
        <UAlert
          v-if="sessionsRequestError && hasOsAuth"
          color="error"
          variant="subtle"
          class="shrink-0"
          :description="sessionsRequestError"
        />

        <UAlert
          v-if="!hasOsAuth"
          color="warning"
          variant="subtle"
          class="rounded-lg border-dashed"
          :description="t('sessions.needLogin')"
        />

        <div
          v-else
          class="overflow-hidden rounded-lg border border-default bg-default shadow-sm"
        >
          <!-- 与 Nuxt Table 文档示例类似：紧贴表格的薄工具条，避免 UCard header 大 padding 造成「离表太远」 -->
          <div
            class="flex min-h-12 flex-nowrap items-center justify-between gap-3 overflow-x-auto border-b border-default px-3 py-3 sm:min-h-14 sm:px-4 sm:py-3.5"
          >
            <span class="shrink-0 text-xs text-muted-foreground">
              {{
                loadingSessions
                  ? t("common.loading")
                  : t("common.itemsInTable", { count: sessions.length })
              }}
            </span>
            <div
              class="flex shrink-0 items-center justify-end gap-2 sm:gap-3"
            >
              <UButton
                v-if="selectedCount === 0"
                color="neutral"
                variant="outline"
                size="sm"
                square
                icon="i-lucide-refresh-cw"
                :aria-label="t('sessions.refreshTitle')"
                :title="t('sessions.refreshTitle')"
                :disabled="loadingAgents || loadingSessions"
                :loading="loadingAgents || loadingSessions"
                class="shrink-0"
                @click="void refreshAll()"
              />
              <template v-if="selectedCount > 0 && !deleteConfirmOpen">
                <span
                  class="shrink-0 text-xs tabular-nums text-muted-foreground"
                  role="status"
                  aria-live="polite"
                >
                  {{ t("sessions.selectedCount", { count: selectedCount }) }}
                </span>
                <UButton
                  variant="outline"
                  color="neutral"
                  size="sm"
                  type="button"
                  class="shrink-0"
                  :disabled="deleting"
                  @click="clearSelection"
                >
                  {{ t("common.cancel") }}
                </UButton>
                <UButton
                  type="button"
                  color="error"
                  variant="solid"
                  size="sm"
                  class="shrink-0"
                  :disabled="deleting"
                  @click="openDeleteConfirm"
                >
                  {{ t("common.delete") }}
                </UButton>
              </template>
            </div>
          </div>

          <UTable
            v-model:sorting="sorting"
            v-model:row-selection="rowSelection"
            :data="sessions"
            :columns="columns"
            :loading="loadingSessions"
            :get-row-id="(row: SessionEntry) => sid(row)"
            :empty="t('sessions.empty')"
            sticky="header"
            class="w-full min-w-0"
            :ui="sessionsTableUi"
          >
            <template #loading>
              <span class="text-muted-foreground">{{
                t("sessions.loading")
              }}</span>
            </template>
          </UTable>
        </div>

        <UModal
          v-model:open="deleteConfirmOpen"
          :title="t('sessions.deleteTitle', { count: selectedCount })"
          :description="t('sessions.deleteHint')"
          :close="false"
        >
          <template #footer>
            <div class="flex w-full justify-end gap-2">
              <UButton
                color="neutral"
                variant="outline"
                type="button"
                :disabled="deleting"
                @click="deleteConfirmOpen = false"
              >
                {{ t("common.cancel") }}
              </UButton>
              <UButton
                color="error"
                type="button"
                :loading="deleting"
                :disabled="deleting"
                @click="void confirmDeleteSessions()"
              >
                {{ deleting ? t("sessions.deleting") : t("common.delete") }}
              </UButton>
            </div>
          </template>
        </UModal>
      </div>
    </div>
  </div>
</template>
