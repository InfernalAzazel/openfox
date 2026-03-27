<script setup lang="ts">
import {
  createScheduleAPI,
  deleteScheduleAPI,
  disableScheduleAPI,
  enableScheduleAPI,
  listScheduleRunsAPI,
  listSchedulesAPI,
  patchScheduleAPI,
  triggerScheduleAPI,
} from "@/api/schedules"
import { getAgentsAPI } from "@/api/os"
import AppPageScaffold from "@/components/AppPageScaffold.vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { getAgentOsBaseUrl } from "@/composables/request"
import { useAppState } from "@/composables/store"
import { cn } from "@/lib/utils"
import type { ScheduleResponse, ScheduleRunResponse } from "@/types/schedules"
import { Calendar, ChevronDown, ExternalLink, Info, RefreshCw, X } from "lucide-vue-next"
import { computed, onMounted, ref, watch } from "vue"
import { useI18n } from "vue-i18n"

export interface ScheduleRunEntry {
  /** 列表项主键（`ScheduleRunResponse.id`） */
  entryId: string
  runId: string
  status: "SUCCESS" | "FAILED"
  triggeredAt: Date
  completedAt: Date
  statusCode: number
  attempt: number
  sessionId: string
  inputSummary: string
  inputHref: string
  outputText: string
  durationMs: number
}

export interface ScheduleRow {
  id: string
  enabled: boolean
  name: string
  cron: string
  endpoint: string
  httpMethod: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  /** JSON 字符串，用于表单编辑 */
  payloadText: string
  description: string
  timezone: string
  /** 高级：请求超时（秒） */
  timeoutSeconds: number
  /** 高级：失败重试次数 */
  maxRetries: number
  /** 高级：重试间隔（秒） */
  retryDelaySeconds: number
  nextRun: Date
  updatedAt: Date
  runsCount: number
}

export interface CreateScheduleForm {
  name: string
  cron: string
  endpointType: string
  endpointPath: string
  customEndpointUrl: string
  httpMethod: ScheduleRow["httpMethod"]
  payloadText: string
  description: string
  timezone: string
  timeoutSeconds: number
  maxRetries: number
  retryDelaySeconds: number
}

export interface ScheduleDraft {
  id: string
  name: string
  cron: string
  endpoint: string
  httpMethod: ScheduleRow["httpMethod"]
  payloadText: string
  description: string
  timezone: string
  timeoutSeconds: number
  maxRetries: number
  retryDelaySeconds: number
}

const timezoneOptions = [
  { value: "Asia/Shanghai", label: "Asia/Shanghai UTC+8" },
  { value: "UTC", label: "UTC UTC+0" },
  { value: "America/New_York", label: "America/New_York UTC−5/−4" },
] as const

const { t, locale } = useI18n()

const endpointTypeOptions = computed(() => [
  { value: "agent", label: t("scheduler.create.typeAgent") },
])

function defaultCreateForm(): CreateScheduleForm {
  return {
    name: "",
    cron: "",
    endpointType: "agent",
    endpointPath: "",
    customEndpointUrl: "",
    httpMethod: "POST",
    payloadText: `{"key": "value"}`,
    description: "",
    timezone: "UTC",
    timeoutSeconds: 3600,
    maxRetries: 0,
    retryDelaySeconds: 60,
  }
}

const app = useAppState()

const rows = ref<ScheduleRow[]>([])
const schedulesLoading = ref(false)
const schedulesError = ref<string | null>(null)
const runsLoading = ref(false)
const runHistoryList = ref<ScheduleRunEntry[]>([])

const selectedId = ref<string | null>(null)
const draft = ref<ScheduleDraft | null>(null)
const detailTab = ref<"details" | "runs">("details")
/** 默认展开，与参考稿一致 */
const advancedOpen = ref(true)
/** RUNS 手风琴：同时仅展开一条 */
const expandedRunId = ref<string | null>(null)

const createDialogOpen = ref(false)
const createForm = ref<CreateScheduleForm>(defaultCreateForm())
/** 创建弹窗内「高级」区块，默认可折叠 */
const createAdvancedOpen = ref(false)

/** 创建页「Agent」类型下：从 OS 拉取的 agent 列表（用于 Selection） */
const createAgentsForPicker = ref<{ id: string; label: string }[]>([])

const createSelectionOptions = computed(() => {
  const list = createAgentsForPicker.value.filter(
    (a) => String(a.id ?? "").trim() !== "",
  )
  if (list.length > 0) {
    return list.map((a) => ({
      value: `/agents/${encodeURIComponent(a.id.trim())}/runs`,
      label: a.label || a.id,
    }))
  }
  return [{ value: "/agents/OpenFox/runs", label: t("brand.name") }]
})

const createSelectionPlaceholder = computed(() => t("scheduler.selectAgent"))

watch(
  () => createForm.value.endpointType,
  () => {
    createForm.value.endpointPath = ""
    createForm.value.customEndpointUrl = ""
  },
)

/** Selection 选定后，同步填入下方「自定义 Endpoint」输入框（跳过缺少 Agent ID 的非法路径） */
watch(
  () => createForm.value.endpointPath,
  (path) => {
    const p = path?.trim()
    if (p && !/\/agents\/[^/]+\/runs/.test(p)) {
      createForm.value.customEndpointUrl = p
    }
  },
)

async function loadAgentsForCreateForm() {
  const { base, token } = authHeaders()
  if (!base || !token) {
    createAgentsForPicker.value = []
    return
  }
  const agents = await getAgentsAPI(base, token)
  createAgentsForPicker.value = agents.map((a) => ({
    id: a.id,
    label: (a.name?.trim() || a.id).trim(),
  }))
}

const selectedRow = computed(() =>
  rows.value.find((r) => r.id === selectedId.value) ?? null,
)

const hasOsAuth = computed(() => {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim()
  return !!(base && token)
})

function authHeaders(): { base: string; token: string | undefined } {
  return {
    base: getAgentOsBaseUrl(),
    token: app.value.access_token?.trim() || undefined,
  }
}

function normalizeUnixMs(ts: number | null | undefined): number {
  if (ts == null || Number.isNaN(ts)) {
    return Date.now()
  }
  return ts < 1_000_000_000_000 ? ts * 1000 : ts
}

function payloadToText(p: Record<string, unknown> | null): string {
  if (!p || Object.keys(p).length === 0) {
    return "{}"
  }
  try {
    return JSON.stringify(p, null, 2)
  } catch {
    return "{}"
  }
}

function scheduleResponseToRow(s: ScheduleResponse, runsCount = 0): ScheduleRow {
  const method = (s.method || "POST").toUpperCase()
  const allowed = ["GET", "POST", "PUT", "PATCH", "DELETE"] as const
  const httpMethod = (allowed.includes(method as (typeof allowed)[number])
    ? method
    : "POST") as ScheduleRow["httpMethod"]
  return {
    id: s.id,
    enabled: s.enabled,
    name: s.name,
    cron: s.cron_expr,
    endpoint: s.endpoint,
    httpMethod,
    payloadText: payloadToText(s.payload),
    description: s.description ?? "",
    timezone: s.timezone,
    timeoutSeconds: s.timeout_seconds,
    maxRetries: s.max_retries,
    retryDelaySeconds: s.retry_delay_seconds,
    nextRun:
      s.next_run_at != null
        ? new Date(normalizeUnixMs(s.next_run_at))
        : new Date(Number.NaN),
    updatedAt:
      s.updated_at != null
        ? new Date(normalizeUnixMs(s.updated_at))
        : new Date(Number.NaN),
    runsCount,
  }
}

function mapRunResponse(r: ScheduleRunResponse): ScheduleRunEntry {
  const st = (r.status || "").toLowerCase()
  const ok
    = st === "success"
      || st === "completed"
      || (r.status_code != null && r.status_code > 0 && r.status_code < 400)
  const trigMs = normalizeUnixMs(r.triggered_at ?? r.created_at ?? undefined)
  const compMs = normalizeUnixMs(r.completed_at ?? r.triggered_at ?? undefined)

  let inputSummary = "—"
  let inputHref = ""
  if (r.input && typeof r.input === "object") {
    const msg = (r.input as Record<string, unknown>).message
    if (typeof msg === "string") {
      inputSummary = msg.length > 120 ? `${msg.slice(0, 120)}…` : msg
      const m = msg.match(/https?:\/\/[^\s]+/)
      if (m) {
        inputHref = m[0]
      }
    } else {
      try {
        inputSummary = JSON.stringify(r.input).slice(0, 160)
      } catch {
        inputSummary = "—"
      }
    }
  }

  let outputText = "—"
  if (r.output != null && typeof r.output === "object") {
    const o = r.output as Record<string, unknown>
    if (typeof o.content === "string") {
      outputText = o.content
    } else {
      try {
        outputText = JSON.stringify(r.output, null, 2)
      } catch {
        outputText = "—"
      }
    }
  }
  if (r.error?.trim()) {
    outputText
      = outputText === "—"
        ? r.error
        : `${outputText}\n\n${r.error}`
  }

  const runIdDisplay = (r.run_id && r.run_id.trim()) ? r.run_id : r.id

  return {
    entryId: r.id,
    runId: runIdDisplay,
    status: ok ? "SUCCESS" : "FAILED",
    triggeredAt: new Date(trigMs),
    completedAt: new Date(compMs),
    statusCode: r.status_code ?? (ok ? 200 : 500),
    attempt: r.attempt,
    sessionId: r.session_id?.trim() || "—",
    inputSummary,
    inputHref,
    outputText,
    durationMs: Math.max(0, compMs - trigMs),
  }
}

async function refreshSchedules() {
  const { base, token } = authHeaders()
  if (!base || !token) {
    rows.value = []
    return
  }
  schedulesLoading.value = true
  schedulesError.value = null
  try {
    const page = await listSchedulesAPI(base, token, { limit: 500, page: 1 })
    if (!page) {
      schedulesError.value = t("scheduler.errors.loadListFailed")
      rows.value = []
      return
    }
    const counts = new Map(rows.value.map(r => [r.id, r.runsCount] as const))
    rows.value = page.data.map((s) => {
      const row = scheduleResponseToRow(s)
      const c = counts.get(row.id)
      if (c != null && c > 0) {
        row.runsCount = c
      }
      return row
    })
  } finally {
    schedulesLoading.value = false
  }
}

/** 工具栏刷新：先拉列表；若右侧卡片已选中某条，再拉该条的 runs（与「立即执行」后一致） */
const toolbarRefreshInFlight = ref(false)

async function refreshFromToolbar() {
  if (toolbarRefreshInFlight.value) {
    return
  }
  toolbarRefreshInFlight.value = true
  try {
    await refreshSchedules()
    if (selectedId.value) {
      await fetchRunsForSelection({ silent: detailTab.value !== "runs" })
    }
  } finally {
    toolbarRefreshInFlight.value = false
  }
}

async function fetchRunsForSelection(opts?: { silent?: boolean }) {
  const silent = opts?.silent ?? false
  const row = selectedRow.value
  const { base, token } = authHeaders()
  if (!row || !base || !token) {
    runHistoryList.value = []
    return
  }
  if (!silent) {
    runsLoading.value = true
  }
  try {
    const page = await listScheduleRunsAPI(base, token, row.id, {
      limit: 100,
      page: 1,
    })
    if (!page) {
      runHistoryList.value = []
      return
    }
    runHistoryList.value = page.data.map(mapRunResponse)
    row.runsCount = page.meta.total_count
  } finally {
    if (!silent) {
      runsLoading.value = false
    }
  }
}

watch(selectedId, (id) => {
  expandedRunId.value = null
  runHistoryList.value = []
  if (id) {
    // Opening the drawer: one background fetch for badge count (no loading overlay on Details).
    void fetchRunsForSelection({ silent: true })
  }
})

watch([detailTab, selectedId], () => {
  if (detailTab.value === "runs" && selectedId.value) {
    // Second fetch when the user opens the Runs tab (shows loading in that tab).
    void fetchRunsForSelection()
  }
})

watch([detailTab, runHistoryList], () => {
  if (detailTab.value !== "runs") {
    return
  }
  const list = runHistoryList.value
  const cur = expandedRunId.value
  // 默认全部收缩；仅当当前展开项已不在列表（例如刷新后）时收起
  if (cur != null && !list.some(r => r.entryId === cur)) {
    expandedRunId.value = null
  }
})

onMounted(() => {
  void refreshSchedules()
})

function rowToDraft(row: ScheduleRow): ScheduleDraft {
  return {
    id: row.id,
    name: row.name,
    cron: row.cron,
    endpoint: row.endpoint,
    httpMethod: row.httpMethod,
    payloadText: row.payloadText,
    description: row.description,
    timezone: row.timezone,
    timeoutSeconds: row.timeoutSeconds,
    maxRetries: row.maxRetries,
    retryDelaySeconds: row.retryDelaySeconds,
  }
}

function parseNonNegInt(v: unknown, fallback: number): number {
  const n = typeof v === "number" ? v : Number.parseInt(String(v), 10)
  if (!Number.isFinite(n) || n < 0) {
    return fallback
  }
  return Math.floor(n)
}

/** 与 Agno `schedules/schema.py` 中 `_NAME_PATTERN` 一致 */
const SCHEDULE_NAME_PATTERN = /^[a-zA-Z0-9][a-zA-Z0-9 ._-]*$/

function scheduleNameIsValid(name: string): boolean {
  return SCHEDULE_NAME_PATTERN.test(name.trim())
}

const scheduleNameHint = computed(() => t("scheduler.nameHint"))

function openRow(row: ScheduleRow) {
  selectedId.value = row.id
  draft.value = rowToDraft(row)
  detailTab.value = "details"
}

function closeDetail() {
  selectedId.value = null
  draft.value = null
}

async function saveDetail() {
  const d = draft.value
  if (!d) {
    return
  }
  const nm = d.name.trim()
  if (!scheduleNameIsValid(nm)) {
    schedulesError.value = t("scheduler.errors.invalidName", {
      hint: scheduleNameHint.value,
    })
    return
  }
  const { base, token } = authHeaders()
  if (!base || !token) {
    schedulesError.value = t("scheduler.errors.needAuth")
    return
  }
  let payload: Record<string, unknown> | null
  try {
    const pt = d.payloadText.trim()
    payload = pt ? (JSON.parse(pt) as Record<string, unknown>) : {}
  } catch {
    schedulesError.value = t("scheduler.errors.payloadNotJson")
    return
  }
  schedulesError.value = null
  const updated = await patchScheduleAPI(base, token, d.id, {
    name: nm,
    cron_expr: d.cron.trim(),
    endpoint: d.endpoint.trim(),
    method: d.httpMethod,
    description: d.description.trim() || null,
    payload,
    timezone: d.timezone,
    timeout_seconds: Math.min(
      86400,
      Math.max(1, parseNonNegInt(d.timeoutSeconds, 3600)),
    ),
    max_retries: Math.min(10, parseNonNegInt(d.maxRetries, 0)),
    retry_delay_seconds: Math.min(
      3600,
      Math.max(1, parseNonNegInt(d.retryDelaySeconds, 60)),
    ),
  })
  if (!updated) {
    schedulesError.value = t("scheduler.errors.saveFailed")
    return
  }
  const idx = rows.value.findIndex(r => r.id === d.id)
  const rc = idx >= 0 ? rows.value[idx]!.runsCount : 0
  const row = scheduleResponseToRow(updated, rc)
  if (idx >= 0) {
    rows.value[idx] = row
  }
  draft.value = rowToDraft(row)
}

function cancelDetail() {
  closeDetail()
}

function formatPayloadJson() {
  const d = draft.value
  if (!d) {
    return
  }
  try {
    const parsed = JSON.parse(d.payloadText)
    d.payloadText = `${JSON.stringify(parsed, null, 2)}\n`
  } catch {
    /* 非法 JSON 时静默跳过 */
  }
}

function cronToHuman(expr: string): string {
  const s = expr.trim()
  if (s === "* * * * *") {
    return t("scheduler.cron.everyMinute")
  }
  if (s === "*/5 * * * *") {
    return t("scheduler.cron.every5Min")
  }
  if (s === "0 * * * *") {
    return t("scheduler.cron.everyHour")
  }
  if (s === "0 0 * * *") {
    return t("scheduler.cron.dailyMidnight")
  }
  return t("scheduler.cron.custom")
}

const runsHumanLabel = computed(() => {
  const c = draft.value?.cron?.trim() ?? ""
  return cronToHuman(c)
})

function formatUpdatedAt(d: Date): string {
  try {
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

function formatNextRun(d: Date): string {
  return `${formatUpdatedAt(d)} …`
}

function isValidDate(d: Date): boolean {
  return !Number.isNaN(d.getTime())
}

function formatRunTime(d: Date): string {
  return formatUpdatedAt(d)
}

function setRunExpanded(entryId: string, open: boolean) {
  if (open) {
    expandedRunId.value = entryId
  } else if (expandedRunId.value === entryId) {
    expandedRunId.value = null
  }
}

function resetCreateForm() {
  createForm.value = defaultCreateForm()
  createAdvancedOpen.value = false
}

function openCreateDialog() {
  resetCreateForm()
  createDialogOpen.value = true
  void loadAgentsForCreateForm()
}

function formatCreatePayload() {
  const f = createForm.value
  try {
    const parsed = JSON.parse(f.payloadText)
    f.payloadText = `${JSON.stringify(parsed, null, 2)}\n`
  } catch {
    /* 非法 JSON 时跳过 */
  }
}

function cancelCreateDialog() {
  createDialogOpen.value = false
}

async function submitCreateSchedule() {
  const f = createForm.value
  const name = f.name.trim()
  const cron = f.cron.trim()
  const endpoint =
    f.customEndpointUrl.trim()
    || f.endpointPath.trim()
    || "/agents/OpenFox/runs"
  if (!name || !cron || !endpoint) {
    schedulesError.value = t("scheduler.errors.fillRequired")
    return
  }
  if (!scheduleNameIsValid(name)) {
    schedulesError.value = t("scheduler.errors.invalidName", {
      hint: scheduleNameHint.value,
    })
    return
  }
  let payload: Record<string, unknown> | null = null
  try {
    const pt = f.payloadText.trim()
    if (pt) {
      payload = JSON.parse(pt) as Record<string, unknown>
    }
  } catch {
    schedulesError.value = t("scheduler.errors.payloadInvalid")
    return
  }
  const { base, token } = authHeaders()
  if (!base || !token) {
    schedulesError.value = t("scheduler.errors.needAuth")
    return
  }
  schedulesError.value = null
  const created = await createScheduleAPI(base, token, {
    name,
    cron_expr: cron,
    endpoint,
    method: f.httpMethod,
    description: f.description.trim() || null,
    payload,
    timezone: f.timezone,
    timeout_seconds: Math.min(
      86400,
      Math.max(1, parseNonNegInt(f.timeoutSeconds, 3600)),
    ),
    max_retries: Math.min(10, parseNonNegInt(f.maxRetries, 0)),
    retry_delay_seconds: Math.min(
      3600,
      Math.max(1, parseNonNegInt(f.retryDelaySeconds, 60)),
    ),
  })
  if (!created.ok) {
    schedulesError.value = t("scheduler.errors.createFailed", {
      status: created.status,
      message: created.message,
    })
    return
  }
  createDialogOpen.value = false
  await refreshSchedules()
}

async function deleteSchedule() {
  const row = selectedRow.value
  const { base, token } = authHeaders()
  if (!row || !base || !token) {
    return
  }
  schedulesError.value = null
  const ok = await deleteScheduleAPI(base, token, row.id)
  if (!ok) {
    schedulesError.value = t("scheduler.errors.deleteFailed")
    return
  }
  closeDetail()
  await refreshSchedules()
}

async function triggerNow() {
  const row = selectedRow.value
  const { base, token } = authHeaders()
  if (!row || !base || !token) {
    return
  }
  schedulesError.value = null
  const ok = await triggerScheduleAPI(base, token, row.id)
  if (!ok) {
    schedulesError.value = t("scheduler.errors.triggerFailed")
    return
  }
  if (selectedId.value === row.id) {
    await fetchRunsForSelection({ silent: detailTab.value !== "runs" })
  }
}

async function onScheduleEnabled(row: ScheduleRow, enabled: boolean) {
  const prev = row.enabled
  row.enabled = enabled
  const { base, token } = authHeaders()
  if (!base || !token) {
    row.enabled = prev
    return
  }
  schedulesError.value = null
  const ok = enabled
    ? await enableScheduleAPI(base, token, row.id)
    : await disableScheduleAPI(base, token, row.id)
  if (!ok) {
    row.enabled = prev
    schedulesError.value = enabled
      ? t("scheduler.errors.enableFailed")
      : t("scheduler.errors.disableFailed")
    return
  }
  await refreshSchedules()
}
</script>

<template>
  <AppPageScaffold
    content-class="flex min-h-0 flex-col"
  >
    <div
      class="flex min-h-0 w-full flex-1 flex-col gap-4 lg:flex-row lg:items-stretch"
    >
      <!-- 左侧表格（错误与提示在表格卡片上方） -->
      <div
        class="flex min-w-0 flex-1 flex-col gap-3"
        :class="
          selectedId
            ? 'lg:max-w-[calc(100%-min(38rem,min(88vw,calc(100vw-2rem)))-1rem)]'
            : ''
        "
      >
        <p
          v-if="schedulesError"
          class="shrink-0 text-sm text-red-600 dark:text-red-400"
        >
          {{ schedulesError }}
        </p>
        <p
          v-else-if="!hasOsAuth"
          class="shrink-0 rounded-lg border border-dashed border-amber-200/80 bg-amber-50/80 px-4 py-3 text-sm text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-200"
        >
          {{ t("scheduler.needAuthHint") }}
        </p>

        <div
          class="rounded-xl border border-border bg-card shadow-sm"
        >
          <div
            class="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3"
          >
            <span
              class="text-left text-xs font-normal tracking-normal text-muted-foreground"
            >
              {{
                schedulesLoading
                  ? t("common.loading")
                  : t("common.itemsInTable", { count: rows.length })
              }}
            </span>
            <div class="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                class="h-9 rounded-lg border-border bg-muted/50 text-xs font-semibold uppercase tracking-wide text-foreground dark:bg-muted/30"
                type="button"
                @click="openCreateDialog"
              >
                {{ t("scheduler.actions.createSchedule") }}
              </Button>
              <Button
                variant="outline"
                size="icon"
                class="h-9 w-9 shrink-0 rounded-lg border-border bg-muted/50 text-foreground dark:bg-muted/30"
                type="button"
                :title="
                  selectedId
                    ? t('scheduler.refreshTitleAll')
                    : t('scheduler.refreshTitleList')
                "
                :disabled="schedulesLoading || toolbarRefreshInFlight"
                @click="void refreshFromToolbar()"
              >
                <RefreshCw
                  class="size-4 opacity-70"
                  :class="(schedulesLoading || toolbarRefreshInFlight) ? 'animate-spin' : ''"
                  aria-hidden="true"
                />
                <span class="sr-only">{{ t("common.refresh") }}</span>
              </Button>
            </div>
          </div>

          <div class="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow class="border-border hover:bg-transparent">
                  <TableHead
                    class="w-24 text-center text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                  >
                    {{ t("scheduler.table.colEnabled") }}
                  </TableHead>
                  <TableHead
                    class="min-w-40 text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                  >
                    {{ t("scheduler.table.colName") }}
                  </TableHead>
                  <TableHead
                    class="min-w-24 whitespace-nowrap font-mono text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                  >
                    {{ t("scheduler.table.colCron") }}
                  </TableHead>
                  <TableHead
                    class="min-w-48 font-mono text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                  >
                    {{ t("scheduler.table.colEndpoint") }}
                  </TableHead>
                  <TableHead
                    class="min-w-40 text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                  >
                    {{ t("scheduler.table.colNextRun") }}
                  </TableHead>
                  <TableHead
                    class="min-w-40 pr-4 text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                  >
                    {{ t("scheduler.table.colUpdatedAt") }}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow
                  v-for="row in rows"
                  :key="row.id"
                  class="cursor-pointer border-border/80 transition-colors"
                  :class="
                    cn(
                      selectedId === row.id
                        && 'bg-accent text-accent-foreground hover:bg-accent/90 dark:hover:bg-accent/80 [&_td]:!text-accent-foreground',
                      selectedId !== row.id && 'hover:bg-muted/50 dark:hover:bg-white/5',
                    )
                  "
                  @click="openRow(row)"
                >
                  <TableCell class="py-3 text-center" @click.stop>
                    <div class="flex justify-center">
                      <Switch
                        :model-value="row.enabled"
                        :aria-label="
                          row.enabled
                            ? t('scheduler.switch.disableAria', { name: row.name })
                            : t('scheduler.switch.enableAria', { name: row.name })
                        "
                        @update:model-value="(v: boolean) => onScheduleEnabled(row, v)"
                      />
                    </div>
                  </TableCell>
                  <TableCell
                    class="max-w-0 py-3 font-medium text-foreground"
                  >
                    <span class="line-clamp-2 wrap-break-word font-mono text-sm">{{ row.name }}</span>
                  </TableCell>
                  <TableCell
                    class="whitespace-nowrap py-3 font-mono text-sm text-foreground"
                  >
                    {{ row.cron }}
                  </TableCell>
                  <TableCell
                    class="py-3 font-mono text-sm text-foreground"
                  >
                    {{ row.endpoint }}
                  </TableCell>
                  <TableCell
                    class="max-w-48 truncate py-3 text-sm tabular-nums text-foreground"
                    :title="isValidDate(row.nextRun) ? formatUpdatedAt(row.nextRun) : undefined"
                  >
                    {{ isValidDate(row.nextRun) ? formatNextRun(row.nextRun) : "—" }}
                  </TableCell>
                  <TableCell
                    class="whitespace-nowrap py-3 pr-4 text-sm tabular-nums text-muted-foreground"
                  >
                    {{ isValidDate(row.updatedAt) ? formatUpdatedAt(row.updatedAt) : "—" }}
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </div>
      </div>

      <!-- 右侧详情卡片 -->
      <div
        v-if="draft && selectedRow"
        class="flex min-h-[min(70dvh,36rem)] w-full shrink-0 flex-col lg:min-h-0 lg:sticky lg:top-0 lg:w-[min(38rem,min(88vw,calc(100vw-2rem)))]"
      >
        <div
          class="flex max-h-full min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-card shadow-sm"
        >
          <div
            class="flex shrink-0 items-start justify-between gap-2 border-b border-border px-4 py-3"
          >
            <h2
              class="min-w-0 flex-1 truncate pr-2 font-mono text-sm font-semibold text-foreground"
              :title="draft.name"
            >
              {{ draft.name || "—" }}
            </h2>
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              class="shrink-0 rounded-lg border-border"
              :aria-label="t('scheduler.detail.closeAria')"
              @click="closeDetail"
            >
              <X class="size-4" />
            </Button>
          </div>

          <Tabs
            v-model="detailTab"
            class="flex min-h-0 flex-1 flex-col gap-0"
          >
            <TabsList
              class="h-auto w-full shrink-0 justify-start gap-6 rounded-none border-b border-border bg-transparent p-0 px-4"
            >
              <TabsTrigger
                value="details"
                class="rounded-none border-0 border-b-2 border-transparent bg-transparent px-0 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground shadow-none transition-colors hover:text-primary data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-primary data-[state=active]:shadow-none"
              >
                {{ t("scheduler.detail.tabsDetails") }}
              </TabsTrigger>
              <TabsTrigger
                value="runs"
                class="rounded-none border-0 border-b-2 border-transparent bg-transparent px-0 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground shadow-none transition-colors hover:text-primary data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-primary data-[state=active]:shadow-none"
              >
                <span class="inline-flex items-center gap-2">
                  {{ t("scheduler.detail.tabsRuns") }}
                  <Badge
                    variant="secondary"
                    class="h-5 rounded-md px-1.5 text-[10px] font-medium tabular-nums"
                  >
                    {{ selectedRow.runsCount }}
                  </Badge>
                </span>
              </TabsTrigger>
            </TabsList>

            <TabsContent
              value="details"
              class="mt-0 flex min-h-0 flex-1 flex-col overflow-hidden data-[state=inactive]:hidden"
            >
              <div class="min-h-0 flex-1 overflow-y-auto overscroll-y-contain">
                <div class="space-y-4 px-4 py-4">
                  <div class="space-y-1.5">
                    <Label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                    >
                      {{ t("scheduler.detail.name") }}
                    </Label>
                    <Input
                      v-model="draft.name"
                      class="font-mono"
                    />
                    <p class="text-xs text-muted-foreground">
                      {{ scheduleNameHint }}
                    </p>
                  </div>

                  <div class="space-y-1.5">
                    <Label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                    >
                      {{ t("scheduler.detail.cronExpression") }}
                    </Label>
                    <Input
                      v-model="draft.cron"
                      class="font-mono text-sm"
                    />
                    <p class="text-xs text-muted-foreground italic">
                      {{ t("scheduler.detail.cronFormatHint") }}
                    </p>
                  </div>

                  <div class="space-y-1.5">
                    <Label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                    >
                      {{ t("scheduler.detail.runsSummary") }}
                    </Label>
                    <div
                      class="rounded-md border border-border bg-muted/40 px-3 py-2 text-sm text-foreground dark:bg-muted/20"
                    >
                      {{ runsHumanLabel }}
                    </div>
                  </div>

                  <div class="space-y-1.5">
                    <Label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                    >
                      {{ t("scheduler.detail.endpoint") }}
                    </Label>
                    <Input
                      v-model="draft.endpoint"
                      class="font-mono text-sm"
                    />
                  </div>

                  <div class="space-y-1.5">
                    <Label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                    >
                      {{ t("scheduler.detail.httpMethod") }}
                    </Label>
                    <Select v-model="draft.httpMethod">
                      <SelectTrigger class="font-mono">
                        <SelectValue :placeholder="t('scheduler.detail.methodPlaceholder')" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="GET">
                          GET
                        </SelectItem>
                        <SelectItem value="POST">
                          POST
                        </SelectItem>
                        <SelectItem value="PUT">
                          PUT
                        </SelectItem>
                        <SelectItem value="PATCH">
                          PATCH
                        </SelectItem>
                        <SelectItem value="DELETE">
                          DELETE
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div class="space-y-1.5">
                    <div class="flex items-center justify-between gap-2">
                      <div class="flex items-center gap-1.5">
                        <Label
                          class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                        >
                          {{ t("scheduler.detail.payload") }}
                        </Label>
                        <Tooltip>
                          <TooltipTrigger as-child>
                            <button
                              type="button"
                              class="text-muted-foreground/80 outline-none hover:text-muted-foreground"
                              :aria-label="t('scheduler.detail.payloadInfoAria')"
                            >
                              <Info class="size-3.5" />
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="top">
                            {{ t("scheduler.detail.payloadTooltip") }}
                          </TooltipContent>
                        </Tooltip>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        class="h-7 px-2 text-[11px] font-semibold uppercase"
                        @click="formatPayloadJson"
                      >
                        {{ t("scheduler.detail.formatJson") }}
                      </Button>
                    </div>
                    <Textarea
                      v-model="draft.payloadText"
                      class="min-h-36 resize-y font-mono text-xs leading-relaxed"
                    />
                  </div>

                  <div class="space-y-1.5">
                    <Label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                    >
                      {{ t("scheduler.detail.descriptionOptional") }}
                    </Label>
                    <Textarea
                      v-model="draft.description"
                      :placeholder="t('scheduler.detail.descriptionPlaceholder')"
                      class="min-h-18 resize-y text-sm"
                    />
                  </div>

                  <div class="space-y-1.5">
                    <Label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                    >
                      {{ t("scheduler.detail.timezone") }}
                    </Label>
                    <Select v-model="draft.timezone">
                      <SelectTrigger>
                        <SelectValue :placeholder="t('scheduler.detail.timezonePlaceholder')" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem
                          v-for="opt in timezoneOptions"
                          :key="opt.value"
                          :value="opt.value"
                        >
                          {{ opt.label }}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <Collapsible v-model:open="advancedOpen">
                    <CollapsibleTrigger
                      class="flex w-full items-center gap-2 py-1 text-left text-xs font-semibold tracking-wide text-foreground uppercase outline-none hover:opacity-80 dark:text-foreground"
                    >
                      <ChevronDown
                        class="size-4 shrink-0 text-muted-foreground transition-transform duration-200 dark:text-muted-foreground"
                        :class="advancedOpen ? 'rotate-180' : ''"
                      />
                      {{ t("scheduler.detail.advanced") }}
                    </CollapsibleTrigger>
                    <CollapsibleContent class="pt-3 pb-1">
                      <div
                        class="ml-0.5 space-y-4 border-l-2 border-border pl-4"
                      >
                        <div class="space-y-1.5">
                          <Label
                            class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                          >
                            {{ t("scheduler.detail.timeoutSeconds") }}
                          </Label>
                          <Input
                            v-model.number="draft.timeoutSeconds"
                            type="number"
                            min="0"
                            step="1"
                            class="tabular-nums"
                          />
                          <p class="text-xs text-muted-foreground">
                            {{ t("scheduler.detail.timeoutHint") }}
                          </p>
                        </div>
                        <div class="space-y-1.5">
                          <Label
                            class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                          >
                            {{ t("scheduler.detail.maxRetries") }}
                          </Label>
                          <Input
                            v-model.number="draft.maxRetries"
                            type="number"
                            min="0"
                            step="1"
                            class="tabular-nums"
                          />
                          <p class="text-xs text-muted-foreground">
                            {{ t("scheduler.detail.maxRetriesHint") }}
                          </p>
                        </div>
                        <div class="space-y-1.5">
                          <Label
                            class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                          >
                            {{ t("scheduler.detail.retryDelaySeconds") }}
                          </Label>
                          <Input
                            v-model.number="draft.retryDelaySeconds"
                            type="number"
                            min="0"
                            step="1"
                            class="tabular-nums"
                          />
                          <p class="text-xs text-muted-foreground">
                            {{ t("scheduler.detail.retryDelayHint") }}
                          </p>
                        </div>
                      </div>
                    </CollapsibleContent>
                  </Collapsible>

                  <div
                    class="flex items-start gap-3 rounded-lg border border-border bg-muted/50 px-3 py-2.5 dark:bg-muted/25"
                  >
                    <Calendar class="mt-0.5 size-4 shrink-0 text-muted-foreground/70" />
                    <div>
                      <div class="text-[11px] font-medium text-muted-foreground uppercase dark:text-muted-foreground">
                        {{ t("scheduler.detail.updatedAt") }}
                      </div>
                      <div class="text-sm tabular-nums text-foreground">
                        {{
                          isValidDate(selectedRow.updatedAt)
                            ? formatUpdatedAt(selectedRow.updatedAt)
                            : "—"
                        }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </TabsContent>

            <TabsContent
              value="runs"
              class="mt-0 flex min-h-0 flex-1 flex-col overflow-hidden data-[state=inactive]:hidden"
            >
              <div
                v-if="runsLoading"
                class="px-4 py-8 text-center text-sm text-muted-foreground"
              >
                {{ t("scheduler.runs.loading") }}
              </div>
              <div
                v-else-if="runHistoryList.length > 0"
                class="min-h-0 flex-1 overflow-y-auto overscroll-y-contain px-1 py-1"
              >
                <div
                  v-for="run in runHistoryList"
                  :key="run.entryId"
                  class="border-b border-border/80 last:border-b-0"
                >
                  <Collapsible
                    :open="expandedRunId === run.entryId"
                    @update:open="(o: boolean) => setRunExpanded(run.entryId, o)"
                  >
                    <CollapsibleTrigger
                      type="button"
                      :class="
                        cn(
                          'group flex w-full items-center gap-2 px-2 py-3 text-left outline-none transition-colors hover:bg-accent hover:text-accent-foreground',
                          expandedRunId === run.entryId && 'bg-accent text-accent-foreground',
                        )
                      "
                    >
                      <ChevronDown
                        class="size-4 shrink-0 text-muted-foreground transition-transform duration-200 group-hover:text-accent-foreground"
                        :class="
                          expandedRunId === run.entryId
                            ? '-rotate-180 text-accent-foreground'
                            : ''
                        "
                      />
                      <span
                        class="min-w-0 flex-1 truncate font-mono text-[11px] leading-snug transition-colors sm:text-xs"
                        :class="
                          expandedRunId === run.entryId
                            ? 'text-accent-foreground'
                            : 'text-foreground group-hover:text-accent-foreground'
                        "
                      >
                        {{ run.runId }}
                      </span>
                      <Badge
                        v-if="run.status === 'SUCCESS'"
                        class="shrink-0 border-0 bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold tracking-wide text-emerald-800 uppercase dark:bg-emerald-950/55 dark:text-emerald-400"
                      >
                        {{ t("scheduler.runs.statusSuccess") }}
                      </Badge>
                      <Badge
                        v-else
                        variant="destructive"
                        class="shrink-0 px-2 py-0.5 text-[10px] font-semibold tracking-wide uppercase"
                      >
                        {{ t("scheduler.runs.statusFailed") }}
                      </Badge>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <div
                        class="border-l-2 border-border pb-4 pl-4 ml-5 mr-1 space-y-4"
                      >
                        <div class="space-y-1.5">
                          <div
                            class="text-[10px] font-medium uppercase tracking-wide text-muted-foreground"
                          >
                            {{ t("scheduler.runs.input") }}
                          </div>
                          <div
                            class="flex items-center gap-2 rounded-lg border border-border bg-muted/50 px-3 py-2.5 dark:bg-muted/30"
                          >
                            <span class="text-sm text-foreground">{{
                              run.inputSummary
                            }}</span>
                            <a
                              v-if="run.inputHref"
                              :href="run.inputHref"
                              target="_blank"
                              rel="noopener noreferrer"
                              class="inline-flex shrink-0 text-muted-foreground hover:text-foreground"
                              :aria-label="t('scheduler.runs.openLinkAria')"
                              @click.stop
                            >
                              <ExternalLink class="size-3.5" />
                            </a>
                          </div>
                        </div>
                        <div class="space-y-1.5">
                          <div
                            class="text-[10px] font-medium uppercase tracking-wide text-muted-foreground"
                          >
                            {{ t("scheduler.runs.output") }}
                          </div>
                          <div
                            class="rounded-lg border border-border bg-muted/50 px-3 py-2.5 text-sm leading-relaxed whitespace-pre-wrap text-foreground dark:bg-muted/30"
                          >
                            {{ run.outputText }}
                          </div>
                        </div>
                        <dl
                          class="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-2 font-mono text-[11px]"
                        >
                          <dt class="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                            {{ t("scheduler.runs.triggeredAt") }}
                          </dt>
                          <dd class="text-foreground tabular-nums">
                            {{ formatRunTime(run.triggeredAt) }}
                          </dd>
                          <dt class="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                            {{ t("scheduler.runs.completedAt") }}
                          </dt>
                          <dd class="text-foreground tabular-nums">
                            {{ formatRunTime(run.completedAt) }}
                          </dd>
                          <dt class="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                            {{ t("scheduler.runs.statusCode") }}
                          </dt>
                          <dd class="text-foreground tabular-nums">
                            {{ run.statusCode }}
                          </dd>
                          <dt class="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                            {{ t("scheduler.runs.attempt") }}
                          </dt>
                          <dd class="text-foreground tabular-nums">
                            {{ run.attempt }}
                          </dd>
                          <dt class="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                            {{ t("scheduler.runs.runId") }}
                          </dt>
                          <dd class="break-all text-foreground">
                            {{ run.runId }}
                          </dd>
                          <dt class="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                            {{ t("scheduler.runs.sessionId") }}
                          </dt>
                          <dd class="break-all text-foreground">
                            {{ run.sessionId }}
                          </dd>
                        </dl>
                      </div>
                    </CollapsibleContent>
                  </Collapsible>
                </div>
              </div>
              <p
                v-else
                class="px-4 py-6 text-center text-sm text-muted-foreground"
              >
                {{ t("scheduler.runs.noRuns") }}
              </p>
            </TabsContent>
          </Tabs>

          <div
            class="flex shrink-0 flex-wrap items-center justify-between gap-2 border-t border-border bg-card px-3 py-3"
          >
            <div class="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="destructive"
                size="sm"
                class="text-xs font-semibold uppercase"
                @click="deleteSchedule"
              >
                {{ t("common.delete") }}
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                class="text-xs font-semibold uppercase"
                @click="triggerNow"
              >
                {{ t("scheduler.actions.triggerNow") }}
              </Button>
            </div>
            <div class="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                class="text-xs font-semibold uppercase"
                @click="cancelDetail"
              >
                {{ t("common.cancel") }}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                class="text-xs font-semibold uppercase"
                @click="saveDetail"
              >
                {{ t("common.save") }}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <Dialog v-model:open="createDialogOpen">
      <DialogContent
        class="flex max-h-[min(90dvh,56rem)] w-[calc(100vw-1.5rem)] max-w-2xl flex-col gap-0 overflow-hidden border-border p-0 sm:max-w-2xl"
      >
        <DialogHeader
          class="shrink-0 space-y-1 border-b border-border px-6 py-4 pr-14 text-left"
        >
          <DialogTitle class="text-base font-semibold tracking-tight">
            {{ t("scheduler.create.title") }}
          </DialogTitle>
          <DialogDescription class="sr-only">
            {{ t("scheduler.create.descriptionSr") }}
          </DialogDescription>
        </DialogHeader>

        <div
          class="min-h-0 flex-1 overflow-y-auto overscroll-y-contain px-6 py-4"
        >
          <div class="space-y-4">
            <div class="space-y-1.5">
              <Label
                class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
              >
                {{ t("scheduler.detail.name") }}
              </Label>
              <Input
                v-model="createForm.name"
                class="font-mono"
                :placeholder="t('scheduler.create.namePlaceholder')"
              />
              <p class="text-xs text-muted-foreground">
                {{ scheduleNameHint }}
              </p>
            </div>

            <div class="space-y-1.5">
              <Label
                class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
              >
                {{ t("scheduler.detail.cronExpression") }}
              </Label>
              <Input
                v-model="createForm.cron"
                class="font-mono text-sm"
                :placeholder="t('scheduler.create.cronPlaceholder')"
              />
              <p class="text-xs text-muted-foreground">
                {{ t("scheduler.detail.cronFormatHint") }}
              </p>
            </div>

            <div class="space-y-3">
              <div class="grid gap-3 sm:grid-cols-2">
                <div class="space-y-1.5">
                  <Label
                    class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                  >
                    {{ t("scheduler.create.type") }}
                  </Label>
                  <Select v-model="createForm.endpointType">
                    <SelectTrigger class="w-full min-w-0">
                      <SelectValue :placeholder="t('scheduler.create.typePlaceholder')" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem
                        v-for="opt in endpointTypeOptions"
                        :key="opt.value"
                        :value="opt.value"
                      >
                        {{ opt.label }}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div class="space-y-1.5">
                  <Label
                    class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                  >
                    {{ t("scheduler.create.selection") }}
                  </Label>
                  <Select
                    v-model="createForm.endpointPath"
                    :disabled="!createForm.endpointType"
                  >
                    <SelectTrigger class="w-full min-w-0">
                      <SelectValue :placeholder="createSelectionPlaceholder" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem
                        v-for="opt in createSelectionOptions"
                        :key="opt.value"
                        :value="opt.value"
                      >
                        {{ opt.label }}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div class="relative py-1">
                <Separator class="bg-border" />
                <span
                  class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-background px-2 text-[11px] font-medium tracking-wide text-muted-foreground uppercase"
                >
                  {{ t("scheduler.create.orDivider") }}
                </span>
              </div>

              <div class="space-y-1.5">
                <Input
                  v-model="createForm.customEndpointUrl"
                  class="font-mono text-sm"
                  :placeholder="t('scheduler.create.customEndpointPlaceholder')"
                  autocomplete="off"
                />
                <p class="text-xs text-muted-foreground">
                  {{ t("scheduler.create.customEndpointHint") }}
                </p>
              </div>
            </div>

            <div class="space-y-1.5">
              <Label
                class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
              >
                {{ t("scheduler.detail.httpMethod") }}
              </Label>
              <Select v-model="createForm.httpMethod">
                <SelectTrigger class="w-full min-w-0 font-mono">
                  <SelectValue :placeholder="t('scheduler.detail.methodPlaceholder')" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="GET">
                    GET
                  </SelectItem>
                  <SelectItem value="POST">
                    POST
                  </SelectItem>
                  <SelectItem value="PUT">
                    PUT
                  </SelectItem>
                  <SelectItem value="PATCH">
                    PATCH
                  </SelectItem>
                  <SelectItem value="DELETE">
                    DELETE
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div class="space-y-1.5">
              <div class="flex items-center justify-between gap-2">
                <div class="flex items-center gap-1.5">
                  <Label
                    class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                  >
                    {{ t("scheduler.detail.payload") }}
                  </Label>
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <button
                        type="button"
                        class="text-muted-foreground/80 outline-none hover:text-muted-foreground"
                        :aria-label="t('scheduler.detail.payloadInfoAria')"
                      >
                        <Info class="size-3.5" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="top">
                      {{ t("scheduler.create.payloadTooltip") }}
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  class="h-7 px-2 text-[11px] font-semibold uppercase"
                  @click="formatCreatePayload"
                >
                  {{ t("scheduler.detail.formatJson") }}
                </Button>
              </div>
              <Textarea
                v-model="createForm.payloadText"
                class="min-h-32 resize-y font-mono text-xs leading-relaxed"
              />
            </div>

            <div class="space-y-1.5">
              <Label
                class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
              >
                {{ t("scheduler.detail.descriptionOptional") }}
              </Label>
              <Textarea
                v-model="createForm.description"
                :placeholder="t('scheduler.detail.descriptionPlaceholder')"
                class="min-h-18 resize-y text-sm"
              />
            </div>

            <div class="space-y-1.5">
              <Label
                class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
              >
                {{ t("scheduler.detail.timezone") }}
              </Label>
              <Select v-model="createForm.timezone">
                <SelectTrigger class="w-full min-w-0">
                  <SelectValue :placeholder="t('scheduler.detail.timezonePlaceholder')" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem
                    v-for="opt in timezoneOptions"
                    :key="opt.value"
                    :value="opt.value"
                  >
                    {{ opt.label }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Collapsible v-model:open="createAdvancedOpen">
              <CollapsibleTrigger
                class="flex w-full items-center gap-2 py-1 text-left text-xs font-semibold tracking-wide text-foreground uppercase outline-none hover:opacity-80 dark:text-foreground"
              >
                <ChevronDown
                  class="size-4 shrink-0 text-muted-foreground transition-transform duration-200 dark:text-muted-foreground"
                  :class="createAdvancedOpen ? 'rotate-180' : ''"
                />
                {{ t("scheduler.detail.advanced") }}
              </CollapsibleTrigger>
              <CollapsibleContent class="pt-3 pb-1">
                <div
                  class="ml-0.5 space-y-4 border-l-2 border-border pl-4"
                >
                  <div class="space-y-1.5">
                    <Label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                    >
                      {{ t("scheduler.detail.timeoutSeconds") }}
                    </Label>
                    <Input
                      v-model.number="createForm.timeoutSeconds"
                      type="number"
                      min="0"
                      step="1"
                      class="tabular-nums"
                    />
                    <p class="text-xs text-muted-foreground">
                      {{ t("scheduler.detail.timeoutHint") }}
                    </p>
                  </div>
                  <div class="space-y-1.5">
                    <Label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                    >
                      {{ t("scheduler.detail.maxRetries") }}
                    </Label>
                    <Input
                      v-model.number="createForm.maxRetries"
                      type="number"
                      min="0"
                      step="1"
                      class="tabular-nums"
                    />
                    <p class="text-xs text-muted-foreground">
                      {{ t("scheduler.detail.maxRetriesHint") }}
                    </p>
                  </div>
                  <div class="space-y-1.5">
                    <Label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
                    >
                      {{ t("scheduler.detail.retryDelaySeconds") }}
                    </Label>
                    <Input
                      v-model.number="createForm.retryDelaySeconds"
                      type="number"
                      min="0"
                      step="1"
                      class="tabular-nums"
                    />
                    <p class="text-xs text-muted-foreground">
                      {{ t("scheduler.detail.retryDelayHint") }}
                    </p>
                  </div>
                </div>
              </CollapsibleContent>
            </Collapsible>
          </div>
        </div>

        <DialogFooter
          class="shrink-0 flex-row items-center justify-between gap-3 border-t border-border bg-muted/40 px-6 py-4 dark:bg-muted/20 sm:justify-between"
        >
          <Button
            type="button"
            variant="secondary"
            class="text-xs font-semibold uppercase"
            @click="cancelCreateDialog"
          >
            {{ t("common.cancel") }}
          </Button>
          <Button
            type="button"
            class="text-xs font-semibold uppercase"
            @click="submitCreateSchedule"
          >
            {{ t("scheduler.create.submit") }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </AppPageScaffold>
</template>
