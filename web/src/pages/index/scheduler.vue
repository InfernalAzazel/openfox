<script setup lang="ts">
import type { TableColumn } from "@nuxt/ui"
import type { Row } from "@tanstack/vue-table"
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
import { getAgentOsBaseUrl } from "@/composables/request"
import { useAppState } from "@/composables/store"
import type { ScheduleResponse, ScheduleRunResponse } from "@/types/schedules"
import { computed, h, onMounted, ref, resolveComponent, watch } from "vue"
import { useI18n } from "vue-i18n"

export interface ScheduleRunEntry {
  /** 列表项主键（`ScheduleRunResponse.id`） */
  entryId: string
  runId: string
  status: "COMPLETED" | "RUNNING" | "PENDING" | "ERROR" | "CANCELLED" | "PAUSED"
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
const SCHEDULER_PAGE_SIZE = 5
const schedulerPage = ref(1)
const schedulesLoading = ref(false)
const schedulesError = ref<string | null>(null)
const runsLoading = ref(false)
const runHistoryList = ref<ScheduleRunEntry[]>([])

const pagedRows = computed(() => {
  const start = (schedulerPage.value - 1) * SCHEDULER_PAGE_SIZE
  return rows.value.slice(start, start + SCHEDULER_PAGE_SIZE)
})

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

/** Selection 选定后，同步填入下方「自定义 Endpoint」输入框 */
watch(
  () => createForm.value.endpointPath,
  (path) => {
    const p = path?.trim()
    if (p) {
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
  const st = String(r.status || "").trim().toUpperCase()
  let status: ScheduleRunEntry["status"]
  switch (st) {
    case "COMPLETED":
    case "SUCCESS":
      status = "COMPLETED"
      break
    case "RUNNING":
      status = "RUNNING"
      break
    case "PENDING":
      status = "PENDING"
      break
    case "CANCELLED":
    case "CANCELED":
      status = "CANCELLED"
      break
    case "PAUSED":
      status = "PAUSED"
      break
    case "ERROR":
    case "FAILED":
      status = "ERROR"
      break
    default:
      status
        = (r.status_code != null && r.status_code > 0 && r.status_code < 400)
          ? "COMPLETED"
          : "ERROR"
  }
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
    status,
    triggeredAt: new Date(trigMs),
    completedAt: new Date(compMs),
    statusCode: r.status_code ?? (status === "COMPLETED" ? 200 : 500),
    attempt: r.attempt,
    sessionId: r.session_id?.trim() || "—",
    inputSummary,
    inputHref,
    outputText,
    durationMs: Math.max(0, compMs - trigMs),
  }
}

function runStatusBadgeClass(status: ScheduleRunEntry["status"]): string {
  switch (status) {
    case "COMPLETED":
      return "bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-300 font-bold"
    case "RUNNING":
      return "bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300 font-bold"
    case "PENDING":
      return "bg-yellow-100 text-yellow-700 dark:bg-yellow-500/20 dark:text-yellow-300 font-bold"
    case "ERROR":
      return "bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300 font-bold"
    case "CANCELLED":
      return "bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-500/20 dark:text-fuchsia-300 font-bold"
    case "PAUSED":
      return "bg-cyan-100 text-cyan-700 dark:bg-cyan-500/20 dark:text-cyan-300 font-bold"
    default:
      return "font-bold"
  }
}

function runStatusLabel(status: ScheduleRunEntry["status"]): string {
  switch (status) {
    case "COMPLETED":
      return t("scheduler.runs.statusCompleted")
    case "RUNNING":
      return t("scheduler.runs.statusRunning")
    case "PENDING":
      return t("scheduler.runs.statusPending")
    case "ERROR":
      return t("scheduler.runs.statusError")
    case "CANCELLED":
      return t("scheduler.runs.statusCancelled")
    case "PAUSED":
      return t("scheduler.runs.statusPaused")
    default:
      return status
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

watch(
  () => rows.value.length,
  (len) => {
    const max = Math.max(1, Math.ceil(len / SCHEDULER_PAGE_SIZE))
    if (schedulerPage.value > max) schedulerPage.value = max
  },
)

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

const USwitch = resolveComponent("USwitch")

const httpMethodSelectItems = [
  { value: "GET", label: "GET" },
  { value: "POST", label: "POST" },
  { value: "PUT", label: "PUT" },
  { value: "PATCH", label: "PATCH" },
  { value: "DELETE", label: "DELETE" },
] as const

const timezoneSelectItems = computed((): { value: string; label: string }[] =>
  timezoneOptions.map((o) => ({ value: o.value as string, label: o.label })),
)

const detailTabItems = computed(() => {
  const r = selectedRow.value
  return [
    {
      value: "details" as const,
      label: t("scheduler.detail.tabsDetails"),
      slot: "details",
    },
    {
      value: "runs" as const,
      label: t("scheduler.detail.tabsRuns"),
      badge: r?.runsCount ?? 0,
      slot: "runs",
    },
  ]
})

const scheduleTableMeta = computed(() => ({
  class: {
    tr: (row: { original: ScheduleRow }) =>
      [
        "cursor-pointer transition-colors",
        selectedId.value === row.original.id
          ? "[&_td]:!bg-primary/12 dark:[&_td]:!bg-primary/20"
          : "",
      ].filter(Boolean).join(" "),
  },
}))

/** 与 sessions / skills 列表 UTable 一致 */
const schedulerTableUi = {
  root: "overflow-x-auto",
  base: "min-w-full table-fixed",
  thead: "bg-elevated/40",
  th: "border-b border-default py-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground",
  tbody: "divide-y divide-default",
  tr: "odd:bg-default even:bg-elevated/30 hover:bg-elevated/45 dark:even:bg-white/[0.06]",
  td: "py-2 px-3 text-sm align-middle",
  separator: "hidden",
  empty: "py-8 text-sm text-muted-foreground",
  loading: "py-8 text-sm",
}

const scheduleColumns = computed<TableColumn<ScheduleRow>[]>(() => [
  {
    id: "enabled",
    header: t("scheduler.table.colEnabled"),
    meta: {
      class: {
        th: "w-24 text-center",
        td: "w-24 text-center",
      },
    },
    cell: ({ row }) =>
      h(
        "div",
        {
          class: "flex justify-center",
          onClick: (e: Event) => e.stopPropagation(),
        },
        [
          h(USwitch as any, {
            modelValue: row.original.enabled,
            size: "sm",
            "onUpdate:modelValue": (v: boolean) =>
              onScheduleEnabled(row.original, v),
            "aria-label": row.original.enabled
              ? t("scheduler.switch.disableAria", { name: row.original.name })
              : t("scheduler.switch.enableAria", { name: row.original.name }),
          }),
        ],
      ),
    enableSorting: false,
  },
  {
    accessorKey: "name",
    header: t("scheduler.table.colName"),
    meta: {
      class: {
        th: "min-w-40",
        td: "max-w-0 min-w-0",
      },
    },
    cell: ({ row }) =>
      h(
        "span",
        {
          class: "line-clamp-2 wrap-break-word font-mono text-sm",
          title: row.original.name,
        },
        row.original.name,
      ),
  },
  {
    accessorKey: "cron",
    header: t("scheduler.table.colCron"),
    meta: {
      class: {
        th: "min-w-24 whitespace-nowrap",
        td: "whitespace-nowrap font-mono text-sm",
      },
    },
  },
  {
    accessorKey: "endpoint",
    header: t("scheduler.table.colEndpoint"),
    meta: {
      class: {
        th: "min-w-48",
        td: "min-w-48 font-mono text-sm",
      },
    },
  },
  {
    id: "nextRun",
    accessorFn: (r) => r.nextRun,
    header: t("scheduler.table.colNextRun"),
    meta: {
      class: {
        th: "min-w-40",
        td: "max-w-48 truncate tabular-nums text-sm",
      },
    },
    cell: ({ row }) =>
      isValidDate(row.original.nextRun)
        ? formatNextRun(row.original.nextRun)
        : "—",
  },
  {
    id: "updatedAt",
    accessorFn: (r) => r.updatedAt,
    header: t("scheduler.table.colUpdatedAt"),
    meta: {
      class: {
        th: "min-w-40",
        td: "whitespace-nowrap tabular-nums text-sm text-muted-foreground",
      },
    },
    cell: ({ row }) =>
      isValidDate(row.original.updatedAt)
        ? formatUpdatedAt(row.original.updatedAt)
        : "—",
  },
])

function openRow(row: ScheduleRow) {
  selectedId.value = row.id
  draft.value = rowToDraft(row)
  detailTab.value = "details"
}

function onScheduleTableRowSelect(_e: Event, row: Row<ScheduleRow>) {
  openRow(row.original)
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
        <UAlert
          v-if="schedulesError"
          color="error"
          variant="subtle"
          class="shrink-0"
          :description="schedulesError"
        />
        <UAlert
          v-else-if="!hasOsAuth"
          color="warning"
          variant="subtle"
          class="shrink-0 rounded-lg border-dashed"
          :description="t('scheduler.needAuthHint')"
        />

        <div
          class="flex flex-col overflow-hidden rounded-xl border border-default bg-default shadow-sm"
        >
          <div
            class="flex min-h-12 flex-nowrap items-center justify-between gap-3 overflow-x-auto border-b border-default px-3 py-3 sm:min-h-14 sm:px-4 sm:py-3.5"
          >
            <span class="shrink-0 text-xs text-muted-foreground">
              {{
                schedulesLoading
                  ? t("common.loading")
                  : t("common.itemsInTable", { count: rows.length })
              }}
            </span>
            <div class="flex shrink-0 items-center gap-2 sm:gap-3">
              <UButton
                variant="solid"
                color="primary"
                size="sm"
                type="button"
                icon="i-lucide-plus"
                @click="openCreateDialog"
              >
                {{ t("scheduler.actions.createSchedule") }}
              </UButton>
              <UButton
                variant="outline"
                color="neutral"
                type="button"
                icon="i-lucide-refresh-cw"
                size="sm"
                square
                :aria-label="
                  selectedId
                    ? t('scheduler.refreshTitleAll')
                    : t('scheduler.refreshTitleList')
                "
                :title="
                  selectedId
                    ? t('scheduler.refreshTitleAll')
                    : t('scheduler.refreshTitleList')
                "
                :disabled="schedulesLoading || toolbarRefreshInFlight"
                :loading="schedulesLoading || toolbarRefreshInFlight"
                @click="void refreshFromToolbar()"
              />
            </div>
          </div>

          <UTable
            :data="pagedRows"
            :columns="scheduleColumns"
            :meta="scheduleTableMeta"
            :loading="schedulesLoading"
            :empty="t('scheduler.table.emptyTable')"
            :get-row-id="(row: ScheduleRow) => row.id"
            sticky="header"
            class="w-full min-w-0"
            :ui="schedulerTableUi"
            :on-select="onScheduleTableRowSelect"
          >
            <template #loading>
              <span class="text-muted-foreground">{{ t("common.loading") }}</span>
            </template>
          </UTable>
          <div class="flex justify-end border-t border-default px-3 py-2 sm:px-4">
            <UPagination
              v-model:page="schedulerPage"
              :items-per-page="SCHEDULER_PAGE_SIZE"
              :total="rows.length"
              size="sm"
            />
          </div>
        </div>
      </div>

      <!-- 右侧详情卡片 -->
      <div
        v-if="draft && selectedRow"
        class="flex min-h-[min(70dvh,36rem)] w-full shrink-0 flex-col lg:min-h-0 lg:sticky lg:top-0 lg:w-[min(38rem,min(88vw,calc(100vw-2rem)))]"
      >
        <div
          class="flex max-h-full min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-default bg-default shadow-sm"
        >
          <div
            class="flex shrink-0 items-start justify-between gap-2 border-b border-default px-4 py-3"
          >
            <h2
              class="min-w-0 flex-1 truncate pr-2 font-mono text-sm font-semibold text-highlighted"
              :title="draft.name"
            >
              {{ draft.name || "—" }}
            </h2>
            <UButton
              type="button"
              variant="outline"
              color="neutral"
              square
              class="shrink-0 rounded-lg"
              icon="i-lucide-x"
              :aria-label="t('scheduler.detail.closeAria')"
              @click="closeDetail"
            />
          </div>

          <UTabs
            v-model="detailTab"
            :items="detailTabItems"
            value-key="value"
            label-key="label"
            class="flex min-h-0 flex-1 flex-col gap-0"
            :ui="{
              root: 'flex min-h-0 flex-1 flex-col gap-0',
              list: 'relative h-auto w-full shrink-0 justify-start gap-6 rounded-none border-b border-default bg-transparent p-0 px-4',
              /** 默认 TabsIndicator 与自定义下划线叠在一起会错位，仅保留下划线样式 */
              indicator: 'hidden',
              trigger:
                'relative z-10 rounded-none border-0 border-b-2 border-transparent bg-transparent px-0 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted shadow-none ring-0 data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-primary',
              content: 'mt-0 flex min-h-0 flex-1 flex-col overflow-hidden data-[state=inactive]:hidden',
            }"
          >
            <template #details>
              <div class="min-h-0 flex-1 overflow-y-auto overscroll-y-contain">
                <div class="space-y-4 px-4 py-4">
                  <div class="space-y-1.5">
                    <label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted"
                    >
                      {{ t("scheduler.detail.name") }}
                    </label>
                    <UInput
                      v-model="draft.name"
                      class="w-full font-mono"
                    />
                    <p class="text-xs text-muted">
                      {{ scheduleNameHint }}
                    </p>
                  </div>

                  <div class="space-y-1.5">
                    <label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted"
                    >
                      {{ t("scheduler.detail.cronExpression") }}
                    </label>
                    <UInput
                      v-model="draft.cron"
                      class="w-full font-mono text-sm"
                    />
                    <p class="text-xs text-muted italic">
                      {{ t("scheduler.detail.cronFormatHint") }}
                    </p>
                  </div>

                  <div class="space-y-1.5">
                    <label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted"
                    >
                      {{ t("scheduler.detail.runsSummary") }}
                    </label>
                    <div
                      class="rounded-md border border-default bg-elevated/50 px-3 py-2 text-sm text-highlighted"
                    >
                      {{ runsHumanLabel }}
                    </div>
                  </div>

                  <div class="space-y-1.5">
                    <label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted"
                    >
                      {{ t("scheduler.detail.endpoint") }}
                    </label>
                    <UInput
                      v-model="draft.endpoint"
                      class="w-full font-mono text-sm"
                    />
                  </div>

                  <div class="space-y-1.5">
                    <label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted"
                    >
                      {{ t("scheduler.detail.httpMethod") }}
                    </label>
                    <USelect
                      v-model="draft.httpMethod"
                      :items="[...httpMethodSelectItems]"
                      value-key="value"
                      label-key="label"
                      class="w-full font-mono"
                    />
                  </div>

                  <div class="space-y-1.5">
                    <div class="flex items-center justify-between gap-2">
                      <div class="flex items-center gap-1.5">
                        <label
                          class="text-[11px] font-medium uppercase tracking-wide text-muted"
                        >
                          {{ t("scheduler.detail.payload") }}
                        </label>
                        <UTooltip :text="t('scheduler.detail.payloadTooltip')">
                          <UButton
                            type="button"
                            variant="ghost"
                            color="neutral"
                            size="xs"
                            square
                            class="size-7"
                            icon="i-lucide-info"
                            :aria-label="t('scheduler.detail.payloadInfoAria')"
                          />
                        </UTooltip>
                      </div>
                      <UButton
                        type="button"
                        variant="ghost"
                        color="neutral"
                        size="xs"
                        class="h-7 px-2 text-[11px] font-semibold uppercase"
                        @click="formatPayloadJson"
                      >
                        {{ t("scheduler.detail.formatJson") }}
                      </UButton>
                    </div>
                    <UTextarea
                      v-model="draft.payloadText"
                      :rows="8"
                      autoresize
                      class="min-h-36 w-full resize-y font-mono text-xs leading-relaxed"
                    />
                  </div>

                  <div class="space-y-1.5">
                    <label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted"
                    >
                      {{ t("scheduler.detail.descriptionOptional") }}
                    </label>
                    <UTextarea
                      v-model="draft.description"
                      :placeholder="t('scheduler.detail.descriptionPlaceholder')"
                      :rows="3"
                      autoresize
                      class="min-h-18 w-full resize-y text-sm"
                    />
                  </div>

                  <div class="space-y-1.5">
                    <label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted"
                    >
                      {{ t("scheduler.detail.timezone") }}
                    </label>
                    <USelect
                      v-model="draft.timezone"
                      :items="timezoneSelectItems"
                      value-key="value"
                      label-key="label"
                      class="w-full"
                    />
                  </div>

                  <UCollapsible v-model:open="advancedOpen">
                    <button
                      type="button"
                      class="flex w-full items-center gap-2 py-1 text-left text-xs font-semibold tracking-wide text-highlighted uppercase outline-none hover:opacity-80"
                    >
                      <UIcon
                        name="i-lucide-chevron-down"
                        class="size-4 shrink-0 text-muted transition-transform duration-200"
                        :class="advancedOpen ? 'rotate-180' : ''"
                      />
                      {{ t("scheduler.detail.advanced") }}
                    </button>
                    <template #content>
                      <div class="pt-3 pb-1">
                        <div
                          class="ml-0.5 space-y-4 border-l-2 border-default pl-4"
                        >
                          <div class="space-y-1.5">
                            <label
                              class="text-[11px] font-medium uppercase tracking-wide text-muted"
                            >
                              {{ t("scheduler.detail.timeoutSeconds") }}
                            </label>
                            <UInput
                              v-model.number="draft.timeoutSeconds"
                              type="number"
                              min="0"
                              step="1"
                              class="w-full tabular-nums"
                            />
                            <p class="text-xs text-muted">
                              {{ t("scheduler.detail.timeoutHint") }}
                            </p>
                          </div>
                          <div class="space-y-1.5">
                            <label
                              class="text-[11px] font-medium uppercase tracking-wide text-muted"
                            >
                              {{ t("scheduler.detail.maxRetries") }}
                            </label>
                            <UInput
                              v-model.number="draft.maxRetries"
                              type="number"
                              min="0"
                              step="1"
                              class="w-full tabular-nums"
                            />
                            <p class="text-xs text-muted">
                              {{ t("scheduler.detail.maxRetriesHint") }}
                            </p>
                          </div>
                          <div class="space-y-1.5">
                            <label
                              class="text-[11px] font-medium uppercase tracking-wide text-muted"
                            >
                              {{ t("scheduler.detail.retryDelaySeconds") }}
                            </label>
                            <UInput
                              v-model.number="draft.retryDelaySeconds"
                              type="number"
                              min="0"
                              step="1"
                              class="w-full tabular-nums"
                            />
                            <p class="text-xs text-muted">
                              {{ t("scheduler.detail.retryDelayHint") }}
                            </p>
                          </div>
                        </div>
                      </div>
                    </template>
                  </UCollapsible>

                  <div
                    class="flex items-start gap-3 rounded-lg border border-default bg-elevated/50 px-3 py-2.5"
                  >
                    <UIcon
                      name="i-lucide-calendar"
                      class="mt-0.5 size-4 shrink-0 text-muted"
                    />
                    <div>
                      <div class="text-[11px] font-medium uppercase text-muted">
                        {{ t("scheduler.detail.updatedAt") }}
                      </div>
                      <div class="text-sm tabular-nums text-highlighted">
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
            </template>

            <template #runs>
              <div
                v-if="runsLoading"
                class="px-4 py-8 text-center text-sm text-muted"
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
                  class="border-b border-default/80 last:border-b-0"
                >
                  <UCollapsible
                    :open="expandedRunId === run.entryId"
                    @update:open="(o: boolean) => setRunExpanded(run.entryId, o)"
                  >
                    <button
                      type="button"
                      :class="[
                        'group flex w-full items-center gap-2 px-2 py-3 text-left outline-none transition-colors hover:bg-elevated',
                        expandedRunId === run.entryId && 'bg-elevated',
                      ]"
                    >
                      <UIcon
                        name="i-lucide-chevron-down"
                        class="size-4 shrink-0 text-muted transition-transform duration-200 group-hover:text-highlighted"
                        :class="
                          expandedRunId === run.entryId
                            ? '-rotate-180 text-highlighted'
                            : ''
                        "
                      />
                      <span
                        class="min-w-0 flex-1 truncate font-mono text-[11px] leading-snug transition-colors sm:text-xs"
                        :class="
                          expandedRunId === run.entryId
                            ? 'text-highlighted'
                            : 'text-highlighted group-hover:text-highlighted'
                        "
                      >
                        {{ run.runId }}
                      </span>
                      <UBadge
                        color="neutral"
                        variant="subtle"
                        :class="[
                          'shrink-0 px-2 py-0.5 text-[10px] tracking-wide uppercase',
                          runStatusBadgeClass(run.status),
                        ]"
                      >
                        {{ runStatusLabel(run.status) }}
                      </UBadge>
                    </button>
                    <template #content>
                      <div
                        class="border-l-2 border-default pb-4 pl-4 ml-5 mr-1 space-y-4"
                      >
                        <div class="space-y-1.5">
                          <div
                            class="text-[10px] font-medium uppercase tracking-wide text-muted"
                          >
                            {{ t("scheduler.runs.input") }}
                          </div>
                          <div
                            class="flex items-center gap-2 rounded-lg border border-default bg-elevated/50 px-3 py-2.5"
                          >
                            <span class="text-sm text-highlighted">{{
                              run.inputSummary
                            }}</span>
                            <a
                              v-if="run.inputHref"
                              :href="run.inputHref"
                              target="_blank"
                              rel="noopener noreferrer"
                              class="inline-flex shrink-0 text-muted hover:text-highlighted"
                              :aria-label="t('scheduler.runs.openLinkAria')"
                              @click.stop
                            >
                              <UIcon name="i-lucide-external-link" class="size-3.5" />
                            </a>
                          </div>
                        </div>
                        <div class="space-y-1.5">
                          <div
                            class="text-[10px] font-medium uppercase tracking-wide text-muted"
                          >
                            {{ t("scheduler.runs.output") }}
                          </div>
                          <div
                            class="rounded-lg border border-default bg-elevated/50 px-3 py-2.5 text-sm leading-relaxed whitespace-pre-wrap text-highlighted"
                          >
                            {{ run.outputText }}
                          </div>
                        </div>
                        <dl
                          class="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-2 font-mono text-[11px]"
                        >
                          <dt class="text-[10px] font-medium uppercase tracking-wide text-muted">
                            {{ t("scheduler.runs.triggeredAt") }}
                          </dt>
                          <dd class="text-highlighted tabular-nums">
                            {{ formatRunTime(run.triggeredAt) }}
                          </dd>
                          <dt class="text-[10px] font-medium uppercase tracking-wide text-muted">
                            {{ t("scheduler.runs.completedAt") }}
                          </dt>
                          <dd class="text-highlighted tabular-nums">
                            {{ formatRunTime(run.completedAt) }}
                          </dd>
                          <dt class="text-[10px] font-medium uppercase tracking-wide text-muted">
                            {{ t("scheduler.runs.statusCode") }}
                          </dt>
                          <dd class="text-highlighted tabular-nums">
                            {{ run.statusCode }}
                          </dd>
                          <dt class="text-[10px] font-medium uppercase tracking-wide text-muted">
                            {{ t("scheduler.runs.attempt") }}
                          </dt>
                          <dd class="text-highlighted tabular-nums">
                            {{ run.attempt }}
                          </dd>
                          <dt class="text-[10px] font-medium uppercase tracking-wide text-muted">
                            {{ t("scheduler.runs.runId") }}
                          </dt>
                          <dd class="break-all text-highlighted">
                            {{ run.runId }}
                          </dd>
                          <dt class="text-[10px] font-medium uppercase tracking-wide text-muted">
                            {{ t("scheduler.runs.sessionId") }}
                          </dt>
                          <dd class="break-all text-highlighted">
                            {{ run.sessionId }}
                          </dd>
                        </dl>
                      </div>
                    </template>
                  </UCollapsible>
                </div>
              </div>
              <p
                v-else
                class="px-4 py-6 text-center text-sm text-muted"
              >
                {{ t("scheduler.runs.noRuns") }}
              </p>
            </template>
          </UTabs>

          <div
            class="flex shrink-0 flex-wrap items-center justify-between gap-2 border-t border-default bg-default px-3 py-3"
          >
            <div class="flex flex-wrap gap-2">
              <UButton
                type="button"
                color="error"
                variant="solid"
                size="sm"
                class="text-xs font-semibold uppercase"
                @click="deleteSchedule"
              >
                {{ t("common.delete") }}
              </UButton>
              <UButton
                type="button"
                color="neutral"
                variant="subtle"
                size="sm"
                class="text-xs font-semibold uppercase"
                @click="triggerNow"
              >
                {{ t("scheduler.actions.triggerNow") }}
              </UButton>
            </div>
            <div class="flex flex-wrap gap-2">
              <UButton
                type="button"
                color="neutral"
                variant="outline"
                size="sm"
                class="text-xs font-semibold uppercase"
                @click="cancelDetail"
              >
                {{ t("common.cancel") }}
              </UButton>
              <UButton
                type="button"
                color="primary"
                variant="solid"
                size="sm"
                class="text-xs font-semibold uppercase"
                @click="saveDetail"
              >
                {{ t("common.save") }}
              </UButton>
            </div>
          </div>
        </div>
      </div>
    </div>

    <UModal
      v-model:open="createDialogOpen"
      :title="t('scheduler.create.title')"
      scrollable
      class="max-w-2xl"
      :ui="{
        content:
          'flex flex-col max-h-[min(90dvh,56rem)] w-[calc(100vw-1.5rem)] max-w-2xl sm:max-w-2xl',
        body: 'min-w-0 flex-1 overflow-y-auto overscroll-y-contain px-6 py-5',
        footer: 'shrink-0 border-t border-default px-6 py-4',
      }"
    >
      <template #description>
        <span class="sr-only">{{ t("scheduler.create.descriptionSr") }}</span>
      </template>

      <template #body>
        <div class="min-w-0 space-y-4">
          <div class="space-y-1.5">
            <label
              class="text-[11px] font-medium uppercase tracking-wide text-muted"
            >
              {{ t("scheduler.detail.name") }}
            </label>
            <UInput
              v-model="createForm.name"
              class="w-full font-mono"
              :placeholder="t('scheduler.create.namePlaceholder')"
            />
            <p class="text-xs text-muted">
              {{ scheduleNameHint }}
            </p>
          </div>

          <div class="space-y-1.5">
            <label
              class="text-[11px] font-medium uppercase tracking-wide text-muted"
            >
              {{ t("scheduler.detail.cronExpression") }}
            </label>
            <UInput
              v-model="createForm.cron"
              class="w-full font-mono text-sm"
              :placeholder="t('scheduler.create.cronPlaceholder')"
            />
            <p class="text-xs text-muted">
              {{ t("scheduler.detail.cronFormatHint") }}
            </p>
          </div>

          <div class="space-y-3">
            <div class="grid gap-3 sm:grid-cols-2">
              <div class="space-y-1.5">
                <label
                  class="text-[11px] font-medium uppercase tracking-wide text-muted"
                >
                  {{ t("scheduler.create.type") }}
                </label>
                <USelect
                  v-model="createForm.endpointType"
                  :items="endpointTypeOptions"
                  value-key="value"
                  label-key="label"
                  class="w-full min-w-0"
                  :placeholder="t('scheduler.create.typePlaceholder')"
                />
              </div>
              <div class="space-y-1.5">
                <label
                  class="text-[11px] font-medium uppercase tracking-wide text-muted"
                >
                  {{ t("scheduler.create.selection") }}
                </label>
                <USelect
                  v-model="createForm.endpointPath"
                  :items="createSelectionOptions"
                  value-key="value"
                  label-key="label"
                  class="w-full min-w-0"
                  :disabled="!createForm.endpointType"
                  :placeholder="createSelectionPlaceholder"
                />
              </div>
            </div>

            <div class="relative py-1">
              <USeparator class="bg-default" />
              <span
                class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-default px-2 text-[11px] font-medium tracking-wide text-muted uppercase"
              >
                {{ t("scheduler.create.orDivider") }}
              </span>
            </div>

            <div class="space-y-1.5">
              <UInput
                v-model="createForm.customEndpointUrl"
                class="w-full font-mono text-sm"
                :placeholder="t('scheduler.create.customEndpointPlaceholder')"
                autocomplete="off"
              />
              <p class="text-xs text-muted">
                {{ t("scheduler.create.customEndpointHint") }}
              </p>
            </div>
          </div>

          <div class="space-y-1.5">
            <label
              class="text-[11px] font-medium uppercase tracking-wide text-muted"
            >
              {{ t("scheduler.detail.httpMethod") }}
            </label>
            <USelect
              v-model="createForm.httpMethod"
              :items="[...httpMethodSelectItems]"
              value-key="value"
              label-key="label"
              class="w-full font-mono"
            />
          </div>

          <div class="space-y-1.5">
            <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-1.5">
                <label
                  class="text-[11px] font-medium uppercase tracking-wide text-muted"
                >
                  {{ t("scheduler.detail.payload") }}
                </label>
                <UTooltip :text="t('scheduler.create.payloadTooltip')">
                  <UButton
                    type="button"
                    variant="ghost"
                    color="neutral"
                    size="xs"
                    square
                    class="size-7"
                    icon="i-lucide-info"
                    :aria-label="t('scheduler.detail.payloadInfoAria')"
                  />
                </UTooltip>
              </div>
              <UButton
                type="button"
                variant="ghost"
                color="neutral"
                size="xs"
                class="h-7 px-2 text-[11px] font-semibold uppercase"
                @click="formatCreatePayload"
              >
                {{ t("scheduler.detail.formatJson") }}
              </UButton>
            </div>
            <UTextarea
              v-model="createForm.payloadText"
              :rows="6"
              autoresize
              class="min-h-32 w-full resize-y font-mono text-xs leading-relaxed"
            />
          </div>

          <div class="space-y-1.5">
            <label
              class="text-[11px] font-medium uppercase tracking-wide text-muted"
            >
              {{ t("scheduler.detail.descriptionOptional") }}
            </label>
            <UTextarea
              v-model="createForm.description"
              :placeholder="t('scheduler.detail.descriptionPlaceholder')"
              :rows="3"
              autoresize
              class="min-h-18 w-full resize-y text-sm"
            />
          </div>

          <div class="space-y-1.5">
            <label
              class="text-[11px] font-medium uppercase tracking-wide text-muted"
            >
              {{ t("scheduler.detail.timezone") }}
            </label>
            <USelect
              v-model="createForm.timezone"
              :items="timezoneSelectItems"
              value-key="value"
              label-key="label"
              class="w-full"
            />
          </div>

          <UCollapsible v-model:open="createAdvancedOpen">
            <button
              type="button"
              class="flex w-full items-center gap-2 py-1 text-left text-xs font-semibold tracking-wide text-highlighted uppercase outline-none hover:opacity-80"
            >
              <UIcon
                name="i-lucide-chevron-down"
                class="size-4 shrink-0 text-muted transition-transform duration-200"
                :class="createAdvancedOpen ? 'rotate-180' : ''"
              />
              {{ t("scheduler.detail.advanced") }}
            </button>
            <template #content>
              <div class="pt-3 pb-1">
                <div
                  class="ml-0.5 space-y-4 border-l-2 border-default pl-4"
                >
                  <div class="space-y-1.5">
                    <label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted"
                    >
                      {{ t("scheduler.detail.timeoutSeconds") }}
                    </label>
                    <UInput
                      v-model.number="createForm.timeoutSeconds"
                      type="number"
                      min="0"
                      step="1"
                      class="w-full tabular-nums"
                    />
                    <p class="text-xs text-muted">
                      {{ t("scheduler.detail.timeoutHint") }}
                    </p>
                  </div>
                  <div class="space-y-1.5">
                    <label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted"
                    >
                      {{ t("scheduler.detail.maxRetries") }}
                    </label>
                    <UInput
                      v-model.number="createForm.maxRetries"
                      type="number"
                      min="0"
                      step="1"
                      class="w-full tabular-nums"
                    />
                    <p class="text-xs text-muted">
                      {{ t("scheduler.detail.maxRetriesHint") }}
                    </p>
                  </div>
                  <div class="space-y-1.5">
                    <label
                      class="text-[11px] font-medium uppercase tracking-wide text-muted"
                    >
                      {{ t("scheduler.detail.retryDelaySeconds") }}
                    </label>
                    <UInput
                      v-model.number="createForm.retryDelaySeconds"
                      type="number"
                      min="0"
                      step="1"
                      class="w-full tabular-nums"
                    />
                    <p class="text-xs text-muted">
                      {{ t("scheduler.detail.retryDelayHint") }}
                    </p>
                  </div>
                </div>
              </div>
            </template>
          </UCollapsible>
        </div>
      </template>

      <template #footer>
        <div class="flex w-full items-center justify-end gap-2">
          <UButton
            type="button"
            color="neutral"
            variant="outline"
            @click="cancelCreateDialog"
          >
            {{ t("common.cancel") }}
          </UButton>
          <UButton
            type="button"
            color="primary"
            variant="solid"
            @click="submitCreateSchedule"
          >
            {{ t("scheduler.create.submit") }}
          </UButton>
        </div>
      </template>
    </UModal>
  </AppPageScaffold>
</template>
