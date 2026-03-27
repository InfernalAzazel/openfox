<script setup lang="ts">
import { IconRefresh } from "@tabler/icons-vue"
import { ArrowDown, ArrowUp } from "lucide-vue-next"
import { computed, onMounted, ref, watch } from "vue"
import { useI18n } from "vue-i18n"
import {
  deleteSessionAPI,
  getAgentsAPI,
  getAllSessionsAPI,
} from "@/api/os"
import AppPageScaffold from "@/components/AppPageScaffold.vue"
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { getAgentOsBaseUrl } from "@/composables/request"
import { useAppState } from "@/composables/store"
import type { AgentDetails, SessionEntry } from "@/types/os"

const { t, locale } = useI18n()
const app = useAppState()

const agents = ref<AgentDetails[]>([])
const selectedAgentId = ref("")
const sessions = ref<SessionEntry[]>([])
const loadingAgents = ref(false)
const loadingSessions = ref(false)
/** 会话列表请求失败时展示在表格上方（与调度页红字风格一致） */
const sessionsRequestError = ref<string | null>(null)
const deleting = ref(false)
/** 删除确认（AlertDialog 模态，与 shadcn-vue 一致） */
const deleteConfirmOpen = ref(false)

/** 按更新时间排序：新到旧 / 旧到新 */
const dateSortOrder = ref<"date-desc" | "date-asc">("date-desc")

const selectedIds = ref<string[]>([])

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

function sessionTime(s: SessionEntry): number {
  const t = s.updated_at ?? s.created_at ?? 0
  return normalizeMs(t)
}

const sessionRows = computed(() => {
  const list = [...sessions.value]
  const mult = dateSortOrder.value === "date-desc" ? -1 : 1
  list.sort((a, b) => {
    const na = sessionTime(a)
    const nb = sessionTime(b)
    if (na === nb) return 0
    return na < nb ? -mult : mult
  })
  return list
})

const selectedCount = computed(() => selectedIds.value.length)

const dateSortLabel = computed(() => {
  void locale.value
  return dateSortOrder.value === "date-desc"
    ? t("sessions.sortNewestFirst")
    : t("sessions.sortOldestFirst")
})

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

function toggleSelectAll(checked: boolean) {
  if (!checked) {
    selectedIds.value = []
    return
  }
  const keys = sessionRows.value.map(sid).filter(Boolean)
  selectedIds.value = [...new Set(keys)]
}

function rowChecked(rowKey: string): boolean {
  return selectedIds.value.includes(rowKey)
}

function toggleRow(rowKey: string, checked: boolean) {
  if (!rowKey) return
  if (checked && !selectedIds.value.includes(rowKey)) {
    selectedIds.value = [...selectedIds.value, rowKey]
  } else if (!checked) {
    selectedIds.value = selectedIds.value.filter((x) => x !== rowKey)
  }
}

/** 表头：未选 / 部分选 / 全选 */
const headerCheckboxModel = computed<boolean | "indeterminate">(() => {
  const rows = sessionRows.value
  const n = rows.length
  if (!n) return false
  let c = 0
  for (const s of rows) {
    const k = sid(s)
    if (k && selectedIds.value.includes(k)) c++
  }
  if (c === 0) return false
  if (c === n) return true
  return "indeterminate"
})

/** reka-ui Checkbox 用 modelValue，不是 checked */
function onSelectAllModel(v: boolean | "indeterminate") {
  if (v === true) toggleSelectAll(true)
  else toggleSelectAll(false)
}

function onRowModel(id: string, v: boolean | "indeterminate") {
  if (v === "indeterminate") return
  toggleRow(id, v)
}

function clearSelection() {
  selectedIds.value = []
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
    selectedIds.value = []
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
    return
  }
  const dbId = selectedAgent.value?.db_id ?? ""
  loadingSessions.value = true
  sessionsRequestError.value = null
  try {
    const res = await getAllSessionsAPI(base, "agent", agentId, dbId, token)
    if (!res.ok) {
      sessions.value = []
      selectedIds.value = []
      sessionsRequestError.value = t("sessions.requestFailed", {
        message: res.message,
      })
      return
    }
    const list = res.data
    sessions.value = list
    const alive = new Set(list.map((s) => sid(s)).filter(Boolean))
    selectedIds.value = selectedIds.value.filter((id) => alive.has(id))
  } finally {
    loadingSessions.value = false
  }
}

async function refreshAll() {
  await refreshAgents()
  await refreshSessions()
}

onMounted(() => {
  void refreshAll()
})

watch(
  () => [selectedAgentId.value, app.value.access_token] as const,
  () => {
    selectedIds.value = []
    deleteConfirmOpen.value = false
    void refreshSessions()
  },
)

watch(selectedCount, (n) => {
  if (n === 0) deleteConfirmOpen.value = false
})
</script>

<template>
  <AppPageScaffold>
    <div class="w-full space-y-4">
      <div
        class="flex w-full flex-wrap items-end justify-between gap-x-4 gap-y-3"
      >
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
            class="col-start-1 row-start-2 min-w-0 max-w-[min(100%,20rem)] font-mono text-sm leading-snug font-medium whitespace-nowrap text-foreground sm:max-w-[24rem]"
            :title="sessionsHeaderMeta.fullId !== '—' ? sessionsHeaderMeta.fullId : undefined"
          >
            {{ sessionsDbIdEllipsis }}
          </span>
          <span
            class="col-start-2 row-start-2 font-mono text-sm leading-snug font-medium whitespace-nowrap text-foreground"
          >
            {{ sessionsHeaderMeta.table }}
          </span>
        </div>

        <div class="flex min-w-0 flex-wrap items-center gap-2 sm:shrink-0">
          <Select v-model="dateSortOrder">
            <SelectTrigger
              class="h-9 min-w-48 rounded-lg border-border bg-muted/50 text-sm shadow-sm dark:bg-muted/30 dark:shadow-none"
            >
              <span class="shrink-0 text-muted-foreground">{{ t("sessions.sortByPrefix") }}</span>
              <SelectValue class="font-semibold text-foreground">
                {{ dateSortLabel }}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectLabel class="text-muted-foreground text-xs font-semibold">
                  {{ t("sessions.sortGroupDate") }}
                </SelectLabel>
                <SelectItem value="date-desc">
                  <span class="flex w-full items-center justify-between gap-4 pr-2">
                    <span>{{ t("sessions.sortNewestFirst") }}</span>
                    <ArrowDown class="size-4 shrink-0 text-muted-foreground/70" />
                  </span>
                </SelectItem>
                <SelectItem value="date-asc">
                  <span class="flex w-full items-center justify-between gap-4 pr-2">
                    <span>{{ t("sessions.sortOldestFirst") }}</span>
                    <ArrowUp class="size-4 shrink-0 text-muted-foreground/70" />
                  </span>
                </SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="icon"
            class="h-9 w-9 shrink-0 rounded-lg border-border bg-muted/50 text-foreground dark:bg-muted/30"
            :title="t('sessions.refreshTitle')"
            :disabled="loadingAgents || loadingSessions"
            @click="void refreshAll()"
          >
            <IconRefresh class="size-4 opacity-70" />
          </Button>
        </div>
      </div>

      <div class="flex flex-col gap-3">
        <p
          v-if="sessionsRequestError && hasOsAuth"
          class="shrink-0 text-sm text-red-600 dark:text-red-400"
        >
          {{ sessionsRequestError }}
        </p>
        <p
          v-if="!hasOsAuth"
          class="rounded-lg border border-dashed border-amber-200/80 bg-amber-50/80 px-4 py-3 text-sm text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-200"
        >
          {{ t("sessions.needLogin") }}
        </p>

        <div
          v-else
          class="rounded-xl border border-border bg-card shadow-sm"
        >
        <div
          class="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3"
        >
          <span
            class="text-left text-xs font-normal tracking-normal text-muted-foreground"
          >
            {{
              loadingSessions
                ? t("common.loading")
                : t("common.itemsInTable", { count: sessionRows.length })
            }}
          </span>
          <div
            v-if="selectedCount > 0 && !deleteConfirmOpen"
            class="flex flex-wrap items-center justify-end gap-x-3 gap-y-2"
            role="status"
            aria-live="polite"
          >
            <span
              class="text-xs tabular-nums text-muted-foreground"
            >
              {{ t("sessions.selectedCount", { count: selectedCount }) }}
            </span>
            <div class="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                class="h-9 rounded-lg border-border bg-muted/50 text-xs font-semibold uppercase tracking-wide text-foreground dark:bg-muted/30"
                type="button"
                :disabled="deleting"
                @click="clearSelection"
              >
                {{ t("common.cancel") }}
              </Button>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                class="h-9 text-xs font-semibold uppercase tracking-wide"
                :disabled="deleting"
                @click="openDeleteConfirm"
              >
                {{ t("common.delete") }}
              </Button>
            </div>
          </div>
        </div>
        <div class="overflow-x-auto">
        <Table class="table-fixed w-full">
          <TableHeader>
            <TableRow class="border-border hover:bg-transparent">
              <TableHead class="w-10 shrink-0 pl-4">
                <Checkbox
                  :model-value="headerCheckboxModel"
                  :disabled="!sessionRows.length"
                  :aria-label="t('sessions.selectAll')"
                  @update:model-value="onSelectAllModel"
                />
              </TableHead>
              <TableHead
                class="min-w-0 w-[55%] text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
              >
                {{ t("sessions.colSessionName") }}
              </TableHead>
              <TableHead
                class="w-[min(12rem,30%)] shrink-0 pr-4 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
              >
                {{ t("sessions.colUpdatedAt") }}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-if="loadingSessions">
              <TableCell colspan="3" class="px-4 py-10 text-center text-sm text-muted-foreground">
                {{ t("sessions.loading") }}
              </TableCell>
            </TableRow>
            <TableRow v-else-if="!sessionRows.length">
              <TableCell colspan="3" class="px-4 py-10 text-center text-sm text-muted-foreground">
                {{ t("sessions.empty") }}
              </TableCell>
            </TableRow>
            <TableRow
              v-for="(s, idx) in sessionRows"
              v-else
              :key="sid(s) || `row-${idx}`"
              class="border-border/80"
            >
              <TableCell class="w-10 pl-4">
                <Checkbox
                  :model-value="rowChecked(sid(s))"
                  :aria-label="t('sessions.selectRow', { name: displayName(s) })"
                  @update:model-value="(v) => onRowModel(sid(s), v)"
                />
              </TableCell>
              <TableCell
                class="max-w-0 min-w-0 py-3 font-medium text-foreground"
              >
                <span
                  class="block min-w-0 truncate text-sm"
                  :title="displayName(s)"
                >{{ displayName(s) }}</span>
              </TableCell>
              <TableCell
                class="whitespace-nowrap pr-4 text-right text-sm tabular-nums text-muted-foreground"
              >
                {{ formatUpdatedAt(s.updated_at ?? s.created_at) }}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
        </div>

        <AlertDialog v-model:open="deleteConfirmOpen">
          <AlertDialogContent
            class="border-border sm:rounded-xl"
          >
            <AlertDialogHeader>
              <AlertDialogTitle class="text-foreground">
                {{ t("sessions.deleteTitle", { count: selectedCount }) }}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {{ t("sessions.deleteHint") }}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel type="button" :disabled="deleting">
                {{ t("common.cancel") }}
              </AlertDialogCancel>
              <Button
                variant="destructive"
                type="button"
                class="min-w-24"
                :disabled="deleting"
                @click="void confirmDeleteSessions()"
              >
                {{ deleting ? t("sessions.deleting") : t("common.delete") }}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        </div>
      </div>
    </div>
  </AppPageScaffold>
</template>
