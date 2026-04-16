<script setup lang="ts">
import type { TableColumn, TableRow } from "@nuxt/ui"
import { computed, h, onMounted, ref, resolveComponent, watch } from "vue"
import { useI18n } from "vue-i18n"
import { getAgentsAPI } from "@/api/os"
import {
  getTraceDetailAPI,
  listTracesAPI,
  listTraceSessionStatsAPI,
  type TraceDetail,
  type TraceNode,
  type TraceSessionStats,
  type TraceSummary,
} from "@/api/traces"
import { getAgentOsBaseUrl } from "@/composables/request"
import { useAppState } from "@/composables/store"
import type { AgentDetails } from "@/types/os"

const { t } = useI18n()
const app = useAppState()
const toast = useToast()

const agents = ref<AgentDetails[]>([])
const selectedAgentId = ref("")
const activeTab = ref<"runs" | "sessions">("runs")
const traceSearchQuery = ref("")
type TraceTimeFilterKey = "30m" | "1h" | "6h" | "1d" | "7d" | "custom" | "all"
const traceTimeFilter = ref<TraceTimeFilterKey>("all")
const traceTimeFilterOpen = ref(false)
const traceCustomStartDate = ref("")
const traceCustomEndDate = ref("")

const loadingAgents = ref(false)
const loadingRuns = ref(false)
const loadingSessions = ref(false)
const loadingTraceDetail = ref(false)
const requestError = ref<string | null>(null)

const traceRuns = ref<TraceSummary[]>([])
const traceSessions = ref<TraceSessionStats[]>([])

const selectedTrace = ref<TraceDetail | null>(null)
const selectedNodeId = ref<string>("")
const detailTab = ref<"info" | "metadata">("info")
const metadataExpandedMap = ref<Record<string, boolean>>({})
const infoExpandedMap = ref<Record<string, boolean>>({})
const TRACE_PAGE_SIZE = 5
const runsPage = ref(1)
const sessionsPage = ref(1)

const selectedAgent = computed(() =>
  agents.value.find((a) => a.id === selectedAgentId.value),
)

const hasOsAuth = computed(() => {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim()
  return !!(base && token)
})

const tracesHeaderMeta = computed(() => {
  const fullId = selectedAgent.value?.db_id?.trim() || ""
  return {
    fullId: fullId || "—",
    table: "agno_traces",
  }
})

const tracesDbIdEllipsis = computed(() => {
  const id = tracesHeaderMeta.value.fullId
  if (id === "—") return id
  const max = 28
  return id.length <= max ? id : `${id.slice(0, max)}...`
})

function authHeaders() {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim()
  return { base, token }
}

function formatDateTime(raw?: string | null) {
  if (!raw) return "—"
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return raw
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function shortId(v?: string | null) {
  const s = v?.trim()
  if (!s) return "—"
  return s.length > 16 ? `${s.slice(0, 16)}...` : s
}

async function copyText(value: string | null | undefined, fieldLabel: string) {
  const text = value?.trim()
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    toast.add({
      title: t("common.copy"),
      description: t("traces.copySuccess", { field: fieldLabel }),
      color: "success",
    })
  } catch {
    toast.add({
      title: t("common.copy"),
      description: t("traces.copyFailed"),
      color: "error",
    })
  }
}

function statusBadgeColor(status?: string | null) {
  const s = status?.toLowerCase() ?? ""
  if (s === "ok" || s === "success") return "success"
  if (s === "error" || s === "failed") return "error"
  if (s === "running" || s === "processing") return "warning"
  return "neutral"
}

function nodeIconName(node: TraceNode | null | undefined, depth: number) {
  if (!node) return "i-lucide-bot"
  if (depth === 0) return "i-lucide-scan-search"
  const name = node.name.toLowerCase()
  const type = node.type.toLowerCase()
  if (name.includes("knowledge") || type.includes("knowledge")) return "i-lucide-link-2"
  if (name.includes("llm") || type.includes("llm")) return "i-lucide-messages-square"
  return "i-lucide-bot"
}

function nodeIconClass(node: TraceNode | null | undefined, depth: number) {
  if (!node) return "bg-emerald-600 text-white"
  if (depth === 0) return "bg-orange-500 text-white"
  const name = node.name.toLowerCase()
  const type = node.type.toLowerCase()
  if (name.includes("knowledge") || type.includes("knowledge")) return "bg-cyan-500 text-white"
  if (name.includes("llm") || type.includes("llm")) return "bg-violet-600 text-white"
  return "bg-emerald-600 text-white"
}

async function refreshAgents() {
  const { base, token } = authHeaders()
  if (!base || !token) return
  loadingAgents.value = true
  try {
    agents.value = await getAgentsAPI(base, token)
    if (!agents.value.length) {
      selectedAgentId.value = ""
      return
    }
    if (!selectedAgentId.value || !agents.value.some((a) => a.id === selectedAgentId.value)) {
      selectedAgentId.value = agents.value[0]!.id
    }
  } finally {
    loadingAgents.value = false
  }
}

async function refreshTraceRuns() {
  const { base, token } = authHeaders()
  if (!base || !token) return
  loadingRuns.value = true
  requestError.value = null
  try {
    const res = await listTracesAPI(base, token, {
      limit: 100,
      agent_id: selectedAgentId.value || undefined,
      db_id: selectedAgent.value?.db_id || undefined,
    })
    if (!res.ok) {
      requestError.value = t("traces.loadFailed", { message: res.message })
      traceRuns.value = []
      return
    }
    traceRuns.value = res.data.data
  } finally {
    loadingRuns.value = false
  }
}

async function refreshTraceSessions() {
  const { base, token } = authHeaders()
  if (!base || !token) return
  loadingSessions.value = true
  requestError.value = null
  try {
    const res = await listTraceSessionStatsAPI(base, token, {
      limit: 100,
      agent_id: selectedAgentId.value || undefined,
      db_id: selectedAgent.value?.db_id || undefined,
    })
    if (!res.ok) {
      requestError.value = t("traces.loadFailed", { message: res.message })
      traceSessions.value = []
      return
    }
    traceSessions.value = res.data.data
  } finally {
    loadingSessions.value = false
  }
}

async function refreshCurrentTab() {
  if (activeTab.value === "runs") {
    await refreshTraceRuns()
    return
  }
  await refreshTraceSessions()
}

async function openTraceDetail(traceId: string, runId?: string | null) {
  const { base, token } = authHeaders()
  if (!base || !token) return
  loadingTraceDetail.value = true
  try {
    const res = await getTraceDetailAPI(base, token, traceId, {
      run_id: runId || undefined,
      db_id: selectedAgent.value?.db_id || undefined,
    })
    if (!res.ok) {
      toast.add({ title: t("traces.loadDetailFailed", { message: res.message }), color: "error" })
      return
    }
    if (!("tree" in res.data)) {
      toast.add({ title: t("traces.invalidDetail"), color: "error" })
      return
    }
    selectedTrace.value = res.data
    selectedNodeId.value = res.data.tree[0]?.id ?? ""
    detailTab.value = "info"
  } finally {
    loadingTraceDetail.value = false
  }
}

function closeTraceDetail() {
  selectedTrace.value = null
  selectedNodeId.value = ""
  detailTab.value = "info"
}

async function selectRunRow(_e: Event, row: TableRow<TraceSummary>) {
  await openTraceDetail(row.original.trace_id, row.original.run_id)
}

async function selectSessionRow(_e: Event, row: TableRow<TraceSessionStats>) {
  const { base, token } = authHeaders()
  if (!base || !token) return
  loadingTraceDetail.value = true
  try {
    const res = await listTracesAPI(base, token, {
      session_id: row.original.session_id,
      limit: 1,
      db_id: selectedAgent.value?.db_id || undefined,
    })
    if (!res.ok) {
      toast.add({ title: t("traces.loadDetailFailed", { message: res.message }), color: "error" })
      return
    }
    const first = res.data.data[0]
    if (!first) {
      toast.add({ title: t("traces.noTraceInSession"), color: "warning" })
      return
    }
    await openTraceDetail(first.trace_id, first.run_id)
  } finally {
    loadingTraceDetail.value = false
  }
}

type FlatNode = { node: TraceNode; depth: number }

function flattenTraceNodes(nodes: TraceNode[] | null | undefined, depth = 0): FlatNode[] {
  if (!nodes?.length) return []
  const out: FlatNode[] = []
  for (const node of nodes) {
    out.push({ node, depth })
    if (node.spans?.length) {
      out.push(...flattenTraceNodes(node.spans, depth + 1))
    }
  }
  return out
}

const traceFlatNodes = computed(() =>
  flattenTraceNodes(selectedTrace.value?.tree),
)

const selectedFlatNode = computed(() =>
  traceFlatNodes.value.find((n) => n.node.id === selectedNodeId.value)
    ?? traceFlatNodes.value[0]
    ?? null,
)

const selectedNode = computed(() =>
  selectedFlatNode.value?.node
    ?? null,
)

const detailHeaderNode = computed(() =>
  selectedFlatNode.value?.node ?? traceFlatNodes.value[0]?.node ?? null,
)

const detailHeaderNodeDepth = computed(() =>
  selectedFlatNode.value?.depth ?? traceFlatNodes.value[0]?.depth ?? 0,
)

type MetadataItem = {
  key: string
  label: string
  valueText: string
}

function formatMetadataLabel(rawKey: string) {
  return rawKey
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toUpperCase()
}

function formatMetadataValue(value: unknown) {
  if (value == null || value === "") return "—"
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value)
  }
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

const metadataItems = computed<MetadataItem[]>(() => {
  const source = selectedNode.value?.metadata
  if (!source || typeof source !== "object") return []
  return Object.entries(source).map(([key, value]) => ({
    key,
    label: formatMetadataLabel(key),
    valueText: formatMetadataValue(value),
  }))
})

function isMetadataExpanded(key: string) {
  return metadataExpandedMap.value[key] ?? true
}

function toggleMetadataExpanded(key: string) {
  metadataExpandedMap.value[key] = !isMetadataExpanded(key)
}

function isInfoExpanded(key: string) {
  return infoExpandedMap.value[key] ?? true
}

function toggleInfoExpanded(key: string) {
  infoExpandedMap.value[key] = !isInfoExpanded(key)
}

function parseJsonStringRecursively(raw: string): unknown {
  let current: unknown = raw
  // 有些接口会返回“被 JSON.stringify 过的 JSON 字符串”，这里最多递归解两层。
  for (let i = 0; i < 3; i += 1) {
    if (typeof current !== "string") return current
    const text = current.trim()
    if (!text) return ""
    try {
      current = JSON.parse(text)
    } catch {
      return current
    }
  }
  return current
}

function pretty(value: unknown) {
  if (value == null || value === "") return "—"
  const normalized =
    typeof value === "string" ? parseJsonStringRecursively(value) : value
  if (typeof normalized === "string") return normalized
  try {
    return JSON.stringify(normalized, null, 2)
  } catch {
    return String(normalized)
  }
}

function stringifyForCopy(value: unknown) {
  if (value == null || value === "") return ""
  const normalized =
    typeof value === "string" ? parseJsonStringRecursively(value) : value
  if (typeof normalized === "string") return normalized
  try {
    return JSON.stringify(normalized, null, 2)
  } catch {
    return String(normalized)
  }
}

function buildSelectedNodePayload() {
  if (!selectedNode.value) return null
  return selectedNode.value
}

function selectedNodeExportText() {
  const payload = buildSelectedNodePayload()
  if (!payload) return ""
  return JSON.stringify(payload, null, 2)
}

function selectedNodeExportBaseName() {
  const raw = selectedNode.value?.name?.trim() || selectedNode.value?.id?.trim() || "selected-node"
  const safe = raw.replace(/[^\w.-]+/g, "_").replace(/^_+|_+$/g, "")
  return safe || "selected-node"
}

async function copySelectedNode() {
  await copyText(selectedNodeExportText(), t("traces.selectedNode"))
}

function downloadTextFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function buildSelectedNodeCsvText() {
  const payload = buildSelectedNodePayload()
  if (!payload) return ""
  const rows: Array<[string, string]> = [
    ["id", payload.id],
    ["name", payload.name],
    ["type", payload.type],
    ["status", payload.status],
    ["duration", payload.duration],
    ["start_time", payload.start_time],
    ["end_time", payload.end_time],
    ["step_type", payload.step_type ?? ""],
    ["input", stringifyForCopy(payload.input)],
    ["output", stringifyForCopy(payload.output)],
    ["error", stringifyForCopy(payload.error)],
    ["metadata", stringifyForCopy(payload.metadata)],
    ["extra_data", stringifyForCopy(payload.extra_data)],
    ["spans", stringifyForCopy(payload.spans)],
  ]
  const escape = (v: string) => `"${v.replaceAll('"', '""')}"`
  return [
    "field,value",
    ...rows.map(([field, value]) => `${escape(field)},${escape(value)}`),
  ].join("\n")
}

function exportSelectedNodeAsJson() {
  const text = selectedNodeExportText()
  if (!text) return
  try {
    const baseName = selectedNodeExportBaseName()
    downloadTextFile(text, `${baseName}.json`, "application/json;charset=utf-8")
    toast.add({
      title: t("traces.export"),
      description: t("traces.exportSuccess", { field: t("traces.exportJson") }),
      color: "success",
    })
  } catch {
    toast.add({
      title: t("traces.export"),
      description: t("traces.exportFailed"),
      color: "error",
    })
  }
}

function exportSelectedNodeAsCsv() {
  const text = buildSelectedNodeCsvText()
  if (!text) return
  try {
    const baseName = selectedNodeExportBaseName()
    downloadTextFile(text, `${baseName}.csv`, "text/csv;charset=utf-8")
    toast.add({
      title: t("traces.export"),
      description: t("traces.exportSuccess", { field: t("traces.exportCsv") }),
      color: "success",
    })
  } catch {
    toast.add({
      title: t("traces.export"),
      description: t("traces.exportFailed"),
      color: "error",
    })
  }
}

const runColumns = computed<TableColumn<TraceSummary>[]>(() => [
  {
    accessorKey: "name",
    header: t("traces.colRunName"),
    cell: ({ row }) =>
      h("div", { class: "min-w-0" }, [
        h("div", { class: "truncate text-sm text-foreground", title: row.original.name }, row.original.name),
        h("div", { class: "truncate text-xs text-muted-foreground", title: row.original.trace_id }, shortId(row.original.trace_id)),
      ]),
  },
  {
    id: "status",
    header: t("traces.colStatus"),
    cell: ({ row }) =>
      h(resolveComponent("UBadge"), {
        color: statusBadgeColor(row.original.status),
        variant: "subtle",
        label: row.original.status?.toUpperCase() || "—",
      }),
  },
  {
    accessorKey: "duration",
    header: t("traces.colDuration"),
    cell: ({ row }) => row.original.duration || "—",
  },
  {
    accessorKey: "total_spans",
    header: t("traces.colSpans"),
    cell: ({ row }) => String(row.original.total_spans ?? 0),
  },
  {
    accessorKey: "input",
    header: t("traces.colInput"),
    cell: ({ row }) =>
      h(
        "span",
        {
          class: "block max-w-80 truncate text-sm",
          title: row.original.input ?? "",
        },
        row.original.input || "—",
      ),
  },
  {
    id: "created_at",
    accessorFn: (row) => row.created_at,
    header: t("traces.colCreatedAt"),
    cell: ({ row }) => formatDateTime(row.original.created_at),
    meta: {
      class: {
        th: "text-right",
        td: "text-right whitespace-nowrap tabular-nums text-muted-foreground",
      },
    },
  },
])

const sessionColumns = computed<TableColumn<TraceSessionStats>[]>(() => [
  {
    accessorKey: "session_id",
    header: t("traces.colSessionId"),
    cell: ({ row }) =>
      h(
        "span",
        { class: "block truncate text-sm", title: row.original.session_id },
        shortId(row.original.session_id),
      ),
  },
  {
    id: "agent_or_workflow",
    header: t("traces.colAgent"),
    cell: ({ row }) => row.original.agent_id || row.original.workflow_id || row.original.team_id || "—",
  },
  {
    accessorKey: "total_traces",
    header: t("traces.colTraceCount"),
    cell: ({ row }) => String(row.original.total_traces ?? 0),
  },
  {
    accessorKey: "first_trace_at",
    header: t("traces.colFirstTrace"),
    cell: ({ row }) => formatDateTime(row.original.first_trace_at),
  },
  {
    accessorKey: "last_trace_at",
    header: t("traces.colLastTrace"),
    cell: ({ row }) => formatDateTime(row.original.last_trace_at),
  },
])

function includesSearchText(parts: Array<string | null | undefined>, query: string) {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return parts.some((part) => (part || "").toLowerCase().includes(q))
}

function parseTimeMs(raw?: string | null) {
  if (!raw) return Number.NaN
  const ms = new Date(raw).getTime()
  return Number.isNaN(ms) ? Number.NaN : ms
}

function timeFilterStartMs() {
  const now = Date.now()
  const mapping: Record<Exclude<TraceTimeFilterKey, "all" | "custom">, number> = {
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "6h": 6 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
    "7d": 7 * 24 * 60 * 60 * 1000,
  }
  if (traceTimeFilter.value === "all" || traceTimeFilter.value === "custom") return null
  return now - mapping[traceTimeFilter.value]
}

function customRangeStartMs() {
  if (!traceCustomStartDate.value) return null
  return new Date(`${traceCustomStartDate.value}T00:00:00`).getTime()
}

function customRangeEndMs() {
  if (!traceCustomEndDate.value) return null
  return new Date(`${traceCustomEndDate.value}T23:59:59.999`).getTime()
}

function passesTimeFilter(raw?: string | null) {
  const ms = parseTimeMs(raw)
  if (Number.isNaN(ms)) return false

  if (traceTimeFilter.value === "custom") {
    const startMs = customRangeStartMs()
    const endMs = customRangeEndMs()
    if (startMs == null || endMs == null) return true
    return ms >= startMs && ms <= endMs
  }

  const startMs = timeFilterStartMs()
  if (startMs == null) return true
  return ms >= startMs
}

const traceTimeFilterLabel = computed(() => {
  if (traceTimeFilter.value === "custom" && traceCustomStartDate.value && traceCustomEndDate.value) {
    return `${traceCustomStartDate.value.replaceAll("-", "/")} ~ ${traceCustomEndDate.value.replaceAll("-", "/")}`
  }
  const keyMap: Record<TraceTimeFilterKey, string> = {
    "30m": "traces.timeLast30Minutes",
    "1h": "traces.timeLastHour",
    "6h": "traces.timeLast6Hours",
    "1d": "traces.timeLastDay",
    "7d": "traces.timeLast7Days",
    custom: "traces.timeCustomRange",
    all: "traces.timeAll",
  }
  return t(keyMap[traceTimeFilter.value])
})

function selectTraceTimeFilter(key: TraceTimeFilterKey) {
  traceTimeFilter.value = key
  traceTimeFilterOpen.value = false
}

function applyTraceCustomRange() {
  const startMs = customRangeStartMs()
  const endMs = customRangeEndMs()
  if (startMs == null || endMs == null) {
    toast.add({ title: t("traces.timeCustomRange"), description: t("traces.timeRangeRequired"), color: "warning" })
    return
  }
  if (startMs > endMs) {
    toast.add({ title: t("traces.timeCustomRange"), description: t("traces.timeRangeInvalid"), color: "warning" })
    return
  }
  traceTimeFilter.value = "custom"
  traceTimeFilterOpen.value = false
}

const filteredTraceRuns = computed(() => {
  const q = traceSearchQuery.value
  return traceRuns.value.filter((row) =>
    passesTimeFilter(row.created_at || row.start_time)
    && includesSearchText([
      row.name,
      row.trace_id,
      row.run_id,
      row.session_id,
      row.status,
      row.duration,
      row.input,
      row.user_id,
      row.agent_id,
      row.workflow_id,
      row.team_id,
      row.created_at,
    ], q),
  )
})

const filteredTraceSessions = computed(() => {
  const q = traceSearchQuery.value
  return traceSessions.value.filter((row) =>
    passesTimeFilter(row.last_trace_at || row.first_trace_at)
    && includesSearchText([
      row.session_id,
      row.user_id,
      row.agent_id,
      row.workflow_id,
      row.team_id,
      String(row.total_traces),
      row.first_trace_at,
      row.last_trace_at,
    ], q),
  )
})

const pagedTraceRuns = computed(() => {
  const start = (runsPage.value - 1) * TRACE_PAGE_SIZE
  return filteredTraceRuns.value.slice(start, start + TRACE_PAGE_SIZE)
})

const pagedTraceSessions = computed(() => {
  const start = (sessionsPage.value - 1) * TRACE_PAGE_SIZE
  return filteredTraceSessions.value.slice(start, start + TRACE_PAGE_SIZE)
})

const activeTraceTableCount = computed(() =>
  activeTab.value === "runs"
    ? filteredTraceRuns.value.length
    : filteredTraceSessions.value.length,
)

const activeTraceTableLoading = computed(() =>
  activeTab.value === "runs" ? loadingRuns.value : loadingSessions.value,
)

function exportRowsAsCsv(rows: Record<string, unknown>[]) {
  if (!rows.length) return ""
  const headers = Object.keys(rows[0]!)
  const escape = (v: string) => `"${v.replaceAll('"', '""')}"`
  const line = (values: string[]) => values.map(escape).join(",")
  return [
    line(headers),
    ...rows.map((row) => line(headers.map((key) => stringifyForCopy(row[key])))),
  ].join("\n")
}

function exportCurrentListAsJson() {
  const rows = activeTab.value === "runs" ? filteredTraceRuns.value : filteredTraceSessions.value
  if (!rows.length) {
    toast.add({ title: t("traces.export"), description: t("traces.noDataToExport"), color: "warning" })
    return
  }
  const text = JSON.stringify(rows, null, 2)
  const filename = `traces-${activeTab.value}-${Date.now()}.json`
  downloadTextFile(text, filename, "application/json;charset=utf-8")
  toast.add({
    title: t("traces.export"),
    description: t("traces.exportSuccess", { field: t("traces.exportJson") }),
    color: "success",
  })
}

function exportCurrentListAsCsv() {
  const rows = activeTab.value === "runs" ? filteredTraceRuns.value : filteredTraceSessions.value
  if (!rows.length) {
    toast.add({ title: t("traces.export"), description: t("traces.noDataToExport"), color: "warning" })
    return
  }
  const text = exportRowsAsCsv(rows as unknown as Record<string, unknown>[])
  const filename = `traces-${activeTab.value}-${Date.now()}.csv`
  downloadTextFile(text, filename, "text/csv;charset=utf-8")
  toast.add({
    title: t("traces.export"),
    description: t("traces.exportSuccess", { field: t("traces.exportCsv") }),
    color: "success",
  })
}

const tableUi = {
  root: "overflow-x-auto",
  base: "min-w-full table-fixed",
  thead: "bg-elevated/40",
  th: "border-b border-default py-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground",
  tbody: "divide-y divide-default",
  tr: "odd:bg-default even:bg-elevated/30 hover:bg-elevated/45 cursor-pointer dark:even:bg-white/[0.06]",
  td: "py-2.5 px-3 text-sm align-middle",
  separator: "hidden",
  empty: "py-8 text-sm text-muted-foreground",
  loading: "py-8 text-sm",
}

onMounted(() => {
  if (!hasOsAuth.value) return
  void refreshAgents().then(() => refreshCurrentTab())
})

watch(
  () => [selectedAgentId.value, app.value.access_token, activeTab.value] as const,
  () => {
    if (!hasOsAuth.value) return
    closeTraceDetail()
    void refreshCurrentTab()
  },
)

watch(
  () => [traceSearchQuery.value, traceTimeFilter.value, traceCustomStartDate.value, traceCustomEndDate.value] as const,
  () => {
    runsPage.value = 1
    sessionsPage.value = 1
  },
)

watch(
  () => filteredTraceRuns.value.length,
  (len) => {
    const max = Math.max(1, Math.ceil(len / TRACE_PAGE_SIZE))
    if (runsPage.value > max) runsPage.value = max
  },
)

watch(
  () => filteredTraceSessions.value.length,
  (len) => {
    const max = Math.max(1, Math.ceil(len / TRACE_PAGE_SIZE))
    if (sessionsPage.value > max) sessionsPage.value = max
  },
)
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col overflow-auto bg-background">
    <div class="w-full space-y-4 p-4 text-foreground md:p-6">
      <div class="flex w-full flex-wrap items-end gap-x-4 gap-y-3">
        <div
          class="inline-grid min-w-0 max-w-full grid-cols-[auto_auto] grid-rows-[auto_auto] gap-x-3 gap-y-0.5 sm:max-w-[min(100%,36rem)] sm:gap-x-4"
        >
          <span class="col-start-1 row-start-1 text-xs leading-none text-muted-foreground">
            {{ t("common.metaDatabase") }}
          </span>
          <span class="col-start-2 row-start-1 text-xs leading-none text-muted-foreground">
            {{ t("common.metaTable") }}
          </span>
          <span
            class="col-start-1 row-start-2 min-w-0 max-w-[min(100%,20rem)] font-mono text-sm leading-snug font-medium whitespace-nowrap sm:max-w-[24rem]"
            :title="tracesHeaderMeta.fullId !== '—' ? tracesHeaderMeta.fullId : undefined"
          >
            {{ tracesDbIdEllipsis }}
          </span>
          <span class="col-start-2 row-start-2 font-mono text-sm leading-snug font-medium whitespace-nowrap">
            {{ tracesHeaderMeta.table }}
          </span>
        </div>
      </div>

      <UAlert
        v-if="requestError && hasOsAuth"
        color="error"
        variant="subtle"
        :description="requestError"
      />

      <UAlert
        v-if="!hasOsAuth"
        color="warning"
        variant="subtle"
        class="rounded-lg border-dashed"
        :description="t('traces.needLogin')"
      />

      <div
        v-else
        class="overflow-hidden rounded-lg border border-default bg-default shadow-sm"
      >
        <div
          v-if="!selectedTrace"
          class="flex min-h-12 items-center justify-between gap-3 border-b border-default px-3 py-2.5 sm:px-4"
        >
          <div class="flex min-w-0 flex-1 items-center gap-2">
            <span class="shrink-0 text-xs text-muted-foreground">
              {{
                activeTraceTableLoading
                  ? t("common.loading")
                  : t("common.itemsInTable", { count: activeTraceTableCount })
              }}
            </span>
            <div class="inline-flex rounded-xl bg-muted p-0.5">
              <button
                type="button"
                class="rounded-lg px-3 py-1.5 text-xs font-medium uppercase tracking-wide transition-colors"
                :class="activeTab === 'runs'
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'"
                @click="activeTab = 'runs'"
              >
                {{ t("traces.tabRuns") }}
              </button>
              <button
                type="button"
                class="rounded-lg px-3 py-1.5 text-xs font-medium uppercase tracking-wide transition-colors"
                :class="activeTab === 'sessions'
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'"
                @click="activeTab = 'sessions'"
              >
                {{ t("traces.tabSessions") }}
              </button>
            </div>
            <UInput
              v-model="traceSearchQuery"
              class="min-w-0 flex-1"
              size="sm"
              icon="i-lucide-search"
              :placeholder="t('traces.searchPlaceholder')"
            />
            <UPopover v-model:open="traceTimeFilterOpen" :content="{ align: 'end' }">
              <UButton
                color="neutral"
                variant="outline"
                size="sm"
                trailing-icon="i-lucide-chevron-down"
              >
                {{ traceTimeFilterLabel }}
              </UButton>
              <template #content>
                <div class="min-w-44 rounded-lg p-1">
                  <button
                    type="button"
                    class="flex w-full items-center rounded-md px-2 py-1.5 text-left text-sm hover:bg-elevated"
                    :class="traceTimeFilter === '30m' ? 'bg-elevated text-foreground' : 'text-foreground'"
                    @click="selectTraceTimeFilter('30m')"
                  >
                    {{ t("traces.timeLast30Minutes") }}
                  </button>
                  <button
                    type="button"
                    class="flex w-full items-center rounded-md px-2 py-1.5 text-left text-sm hover:bg-elevated"
                    :class="traceTimeFilter === '1h' ? 'bg-elevated text-foreground' : 'text-foreground'"
                    @click="selectTraceTimeFilter('1h')"
                  >
                    {{ t("traces.timeLastHour") }}
                  </button>
                  <button
                    type="button"
                    class="flex w-full items-center rounded-md px-2 py-1.5 text-left text-sm hover:bg-elevated"
                    :class="traceTimeFilter === '6h' ? 'bg-elevated text-foreground' : 'text-foreground'"
                    @click="selectTraceTimeFilter('6h')"
                  >
                    {{ t("traces.timeLast6Hours") }}
                  </button>
                  <button
                    type="button"
                    class="flex w-full items-center rounded-md px-2 py-1.5 text-left text-sm hover:bg-elevated"
                    :class="traceTimeFilter === '1d' ? 'bg-elevated text-foreground' : 'text-foreground'"
                    @click="selectTraceTimeFilter('1d')"
                  >
                    {{ t("traces.timeLastDay") }}
                  </button>
                  <button
                    type="button"
                    class="flex w-full items-center rounded-md px-2 py-1.5 text-left text-sm hover:bg-elevated"
                    :class="traceTimeFilter === '7d' ? 'bg-elevated text-foreground' : 'text-foreground'"
                    @click="selectTraceTimeFilter('7d')"
                  >
                    {{ t("traces.timeLast7Days") }}
                  </button>
                  <div class="my-1 border-t border-default" />
                  <button
                    type="button"
                    class="flex w-full items-center rounded-md px-2 py-1.5 text-left text-sm hover:bg-elevated"
                    :class="traceTimeFilter === 'all' ? 'bg-elevated text-foreground' : 'text-foreground'"
                    @click="selectTraceTimeFilter('all')"
                  >
                    {{ t("traces.timeAll") }}
                  </button>
                  <div class="my-1 border-t border-default" />
                  <div class="space-y-2 rounded-md px-2 py-2">
                    <p class="text-xs font-medium text-muted-foreground">{{ t("traces.timeCustomRange") }}</p>
                    <div class="grid grid-cols-1 gap-2">
                      <input
                        v-model="traceCustomStartDate"
                        type="date"
                        class="h-8 rounded-md border border-default bg-default px-2 text-sm outline-none focus:border-primary"
                      >
                      <input
                        v-model="traceCustomEndDate"
                        type="date"
                        class="h-8 rounded-md border border-default bg-default px-2 text-sm outline-none focus:border-primary"
                      >
                    </div>
                    <UButton
                      color="primary"
                      variant="soft"
                      size="xs"
                      block
                      @click="applyTraceCustomRange()"
                    >
                      {{ t("traces.timeApplyRange") }}
                    </UButton>
                  </div>
                </div>
              </template>
            </UPopover>
            <UPopover mode="hover" :open-delay="120" :close-delay="120">
              <UButton
                color="neutral"
                variant="outline"
                size="sm"
                icon="i-lucide-upload"
              >
                {{ t("traces.export") }}
              </UButton>
              <template #content>
                <div class="min-w-44 rounded-lg p-1">
                  <button
                    type="button"
                    class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-foreground hover:bg-elevated"
                    @click="exportCurrentListAsCsv()"
                  >
                    <UIcon name="i-lucide-file-spreadsheet" class="size-4 text-muted-foreground" />
                    <span>{{ t("traces.exportCsv") }}</span>
                  </button>
                  <button
                    type="button"
                    class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-foreground hover:bg-elevated"
                    @click="exportCurrentListAsJson()"
                  >
                    <UIcon name="i-lucide-file-json" class="size-4 text-muted-foreground" />
                    <span>{{ t("traces.exportJson") }}</span>
                  </button>
                </div>
              </template>
            </UPopover>
          </div>
          <UButton
            color="neutral"
            variant="outline"
            size="sm"
            square
            icon="i-lucide-refresh-cw"
            :disabled="loadingAgents || loadingRuns || loadingSessions"
            :loading="loadingAgents || loadingRuns || loadingSessions"
            :title="t('common.refresh')"
            @click="void refreshCurrentTab()"
          />
        </div>

        <div v-if="selectedTrace" class="space-y-3 p-3 sm:p-4">
          <div class="flex items-center justify-between gap-3">
            <div class="min-w-0">
              <p class="mt-0.5 flex flex-wrap items-center gap-x-1 gap-y-0.5 text-sm text-foreground">
                {{ t("traces.createdAt") }}: {{ formatDateTime(selectedTrace.created_at) }}
                · {{ t("traces.colTraceId") }}:
                <span class="inline-flex items-center gap-1">
                  <span :title="selectedTrace.trace_id">{{ shortId(selectedTrace.trace_id) }}</span>
                  <UButton
                    color="neutral"
                    variant="ghost"
                    size="xs"
                    square
                    icon="i-lucide-copy"
                    :title="t('common.copy')"
                    @click.stop="void copyText(selectedTrace.trace_id, t('traces.colTraceId'))"
                  />
                </span>
                · {{ t("traces.colRunId") }}:
                <span class="inline-flex items-center gap-1">
                  <span :title="selectedTrace.run_id || undefined">{{ shortId(selectedTrace.run_id) }}</span>
                  <UButton
                    color="neutral"
                    variant="ghost"
                    size="xs"
                    square
                    icon="i-lucide-copy"
                    :title="t('common.copy')"
                    @click.stop="void copyText(selectedTrace.run_id, t('traces.colRunId'))"
                  />
                </span>
                · {{ t("traces.colSessionId") }}:
                <span class="inline-flex items-center gap-1">
                  <span :title="selectedTrace.session_id || undefined">{{ shortId(selectedTrace.session_id) }}</span>
                  <UButton
                    color="neutral"
                    variant="ghost"
                    size="xs"
                    square
                    icon="i-lucide-copy"
                    :title="t('common.copy')"
                    @click.stop="void copyText(selectedTrace.session_id, t('traces.colSessionId'))"
                  />
                </span>
              </p>
            </div>
            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-arrow-left"
              @click="closeTraceDetail()"
            >
              Back
            </UButton>
          </div>

          <div class="grid min-h-128 grid-cols-12 gap-4">
            <div class="col-span-4 min-h-0 overflow-auto rounded-lg border border-default">
              <div class="flex items-center justify-between border-b border-default px-3 py-2 text-xs text-muted-foreground">
                <span>{{ t("traces.spansCount", { count: traceFlatNodes.length }) }}</span>
                <div class="flex items-center gap-1">
                  <UPopover
                    mode="hover"
                    :open-delay="120"
                    :close-delay="120"
                  >
                    <UButton
                      color="neutral"
                      variant="ghost"
                      size="xs"
                      square
                      icon="i-lucide-upload"
                      :title="t('traces.export')"
                      :disabled="!selectedNode"
                    />
                    <template #content>
                      <div class="min-w-44 rounded-lg p-1">
                        <button
                          type="button"
                          class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-foreground hover:bg-elevated"
                          :disabled="!selectedNode"
                          @click="exportSelectedNodeAsCsv()"
                        >
                          <UIcon name="i-lucide-file-spreadsheet" class="size-4 text-muted-foreground" />
                          <span>{{ t("traces.exportCsv") }}</span>
                        </button>
                        <button
                          type="button"
                          class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-foreground hover:bg-elevated"
                          :disabled="!selectedNode"
                          @click="exportSelectedNodeAsJson()"
                        >
                          <UIcon name="i-lucide-file-json" class="size-4 text-muted-foreground" />
                          <span>{{ t("traces.exportJson") }}</span>
                        </button>
                      </div>
                    </template>
                  </UPopover>
                  <UButton
                    color="neutral"
                    variant="ghost"
                    size="xs"
                    square
                    icon="i-lucide-copy"
                    :title="t('common.copy')"
                    :disabled="!selectedNode"
                    @click.stop="void copySelectedNode()"
                  />
                </div>
              </div>
              <div class="divide-y divide-default">
                <button
                  v-for="row in traceFlatNodes"
                  :key="row.node.id"
                  type="button"
                  class="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-elevated/50"
                  :class="selectedNodeId === row.node.id ? 'bg-primary/10' : ''"
                  @click="selectedNodeId = row.node.id"
                >
                  <span
                    class="relative inline-flex h-10 shrink-0 items-center"
                    :style="{ width: `${16 + row.depth * 14}px` }"
                  >
                    <span
                      v-if="row.depth > 0"
                      class="absolute top-0 bottom-0 w-px bg-default"
                      :style="{ left: `${8 + (row.depth - 1) * 14}px` }"
                    />
                    <span
                      class="absolute inline-block size-2 rounded-full bg-muted-foreground/35"
                      :style="{ left: `${4 + row.depth * 14}px` }"
                    />
                  </span>
                  <span
                    class="inline-flex size-8 shrink-0 items-center justify-center rounded-lg"
                    :class="nodeIconClass(row.node, row.depth)"
                  >
                    <UIcon :name="nodeIconName(row.node, row.depth)" class="size-4" />
                  </span>
                  <span class="min-w-0 flex-1 truncate text-sm" :title="row.node.name">
                    {{ row.node.name }}
                  </span>
                  <span class="shrink-0 text-xs text-muted-foreground">{{ row.node.duration }}</span>
                </button>
              </div>
            </div>

            <div class="col-span-8 min-h-0 overflow-auto rounded-lg border border-default">
              <div class="border-b border-default">
                <div class="flex items-center justify-between gap-3 px-4 py-3">
                  <div class="min-w-0 flex items-center gap-3">
                    <span
                      class="inline-flex size-6 items-center justify-center rounded-md"
                      :class="nodeIconClass(detailHeaderNode, detailHeaderNodeDepth)"
                    >
                      <UIcon
                        :name="nodeIconName(detailHeaderNode, detailHeaderNodeDepth)"
                        class="size-3.5"
                      />
                    </span>
                    <span class="truncate text-lg font-medium text-foreground" :title="selectedNode?.name || selectedTrace.name">
                      {{ selectedNode?.name || selectedTrace.name }}
                    </span>
                  </div>
                  <div class="flex items-center gap-2">
                    <span class="text-xs tracking-wider text-muted-foreground">
                      LATENCY
                      <span class="ml-1 text-sm text-foreground">{{ selectedNode?.duration || selectedTrace.duration }}</span>
                    </span>
                    <UBadge
                      :color="statusBadgeColor(selectedNode?.status || selectedTrace.status)"
                      variant="subtle"
                      :label="(selectedNode?.status || selectedTrace.status || '').toUpperCase()"
                    />
                    <UPopover
                      mode="hover"
                      :open-delay="120"
                      :close-delay="120"
                    >
                      <UButton
                        color="neutral"
                        variant="ghost"
                        size="sm"
                        square
                        icon="i-lucide-upload"
                        :title="t('traces.export')"
                        :disabled="!selectedNode"
                      />
                      <template #content>
                        <div class="min-w-44 rounded-lg p-1">
                          <button
                            type="button"
                            class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-foreground hover:bg-elevated"
                            :disabled="!selectedNode"
                            @click="exportSelectedNodeAsCsv()"
                          >
                            <UIcon name="i-lucide-file-spreadsheet" class="size-4 text-muted-foreground" />
                            <span>{{ t("traces.exportCsv") }}</span>
                          </button>
                          <button
                            type="button"
                            class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-foreground hover:bg-elevated"
                            :disabled="!selectedNode"
                            @click="exportSelectedNodeAsJson()"
                          >
                            <UIcon name="i-lucide-file-json" class="size-4 text-muted-foreground" />
                            <span>{{ t("traces.exportJson") }}</span>
                          </button>
                        </div>
                      </template>
                    </UPopover>
                  </div>
                </div>
                <div class="flex items-center gap-6 px-4 pt-1">
                  <button
                    type="button"
                    class="border-b-2 px-1 pb-2 text-sm font-medium tracking-wide"
                    :class="detailTab === 'info' ? 'border-foreground text-foreground' : 'border-transparent text-muted-foreground'"
                    @click="detailTab = 'info'"
                  >
                    {{ t("traces.tabInfo") }}
                  </button>
                  <button
                    type="button"
                    class="border-b-2 px-1 pb-2 text-sm font-medium tracking-wide"
                    :class="detailTab === 'metadata' ? 'border-foreground text-foreground' : 'border-transparent text-muted-foreground'"
                    @click="detailTab = 'metadata'"
                  >
                    {{ t("traces.tabMetadata") }}
                  </button>
                </div>
              </div>

              <div v-if="detailTab === 'info'" class="space-y-4 p-4">
                <div>
                  <div class="mb-1 flex items-center justify-between gap-2">
                    <button
                      type="button"
                      class="flex items-center gap-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                      @click="toggleInfoExpanded('input')"
                    >
                      <UIcon :name="isInfoExpanded('input') ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'" />
                      <span>{{ t("traces.input") }}</span>
                    </button>
                  </div>
                  <div v-if="isInfoExpanded('input')" class="relative">
                    <UButton
                      color="neutral"
                      variant="ghost"
                      size="sm"
                      square
                      icon="i-lucide-copy"
                      :title="t('common.copy')"
                      class="absolute top-2 right-2 z-10"
                      @click.stop="void copyText(stringifyForCopy(selectedNode?.input ?? selectedTrace.input), t('traces.input'))"
                    />
                    <pre class="max-h-50 overflow-auto rounded-md bg-muted p-3 pr-12 text-xs whitespace-pre-wrap">{{ pretty(selectedNode?.input ?? selectedTrace.input) }}</pre>
                  </div>
                </div>
                <div>
                  <div class="mb-1 flex items-center justify-between gap-2">
                    <button
                      type="button"
                      class="flex items-center gap-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                      @click="toggleInfoExpanded('output')"
                    >
                      <UIcon :name="isInfoExpanded('output') ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'" />
                      <span>{{ t("traces.output") }}</span>
                    </button>
                  </div>
                  <div v-if="isInfoExpanded('output')" class="relative">
                    <UButton
                      color="neutral"
                      variant="ghost"
                      size="sm"
                      square
                      icon="i-lucide-copy"
                      :title="t('common.copy')"
                      class="absolute top-2 right-2 z-10"
                      @click.stop="void copyText(stringifyForCopy(selectedNode?.output ?? selectedTrace.output), t('traces.output'))"
                    />
                    <pre class="max-h-50 overflow-auto rounded-md bg-muted p-3 pr-12 text-xs whitespace-pre-wrap">{{ pretty(selectedNode?.output ?? selectedTrace.output) }}</pre>
                  </div>
                </div>
                <div v-if="(selectedNode?.error ?? selectedTrace.error)">
                  <div class="mb-1 flex items-center justify-between gap-2">
                    <button
                      type="button"
                      class="flex items-center gap-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                      @click="toggleInfoExpanded('error')"
                    >
                      <UIcon :name="isInfoExpanded('error') ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'" />
                      <span>{{ t("traces.error") }}</span>
                    </button>
                  </div>
                  <div v-if="isInfoExpanded('error')" class="relative">
                    <UButton
                      color="neutral"
                      variant="ghost"
                      size="sm"
                      square
                      icon="i-lucide-copy"
                      :title="t('common.copy')"
                      class="absolute top-2 right-2 z-10"
                      @click.stop="void copyText(stringifyForCopy(selectedNode?.error ?? selectedTrace.error), t('traces.error'))"
                    />
                    <pre class="max-h-40 overflow-auto rounded-md bg-muted p-3 pr-12 text-xs whitespace-pre-wrap">{{ pretty(selectedNode?.error ?? selectedTrace.error) }}</pre>
                  </div>
                </div>
              </div>

              <div v-else class="space-y-4 p-4">
                <div class="space-y-4">
                  <div
                    v-for="item in metadataItems"
                    :key="item.key"
                    class="space-y-1"
                  >
                    <button
                      type="button"
                      class="flex w-full items-center gap-2 text-left text-xs font-semibold tracking-wide text-muted-foreground"
                      @click="toggleMetadataExpanded(item.key)"
                    >
                      <UIcon :name="isMetadataExpanded(item.key) ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'" />
                      <span class="uppercase">{{ item.label }}</span>
                    </button>
                    <div v-if="isMetadataExpanded(item.key)" class="flex items-center justify-between gap-2 rounded-md bg-muted px-3 py-2">
                      <span class="min-w-0 truncate text-base text-foreground" :title="item.valueText">
                        {{ item.valueText }}
                      </span>
                      <UButton
                        color="neutral"
                        variant="ghost"
                        size="sm"
                        square
                        icon="i-lucide-copy"
                        :title="t('common.copy')"
                        @click.stop="void copyText(item.valueText, item.label)"
                      />
                    </div>
                  </div>
                  <div v-if="!metadataItems.length" class="rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
                    —
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <UTable
          v-else-if="activeTab === 'runs'"
          :data="pagedTraceRuns"
          :columns="runColumns"
          :loading="loadingRuns || loadingTraceDetail"
          :empty="t('traces.emptyRuns')"
          sticky="header"
          class="w-full min-w-0"
          :ui="tableUi"
          @select="selectRunRow"
        >
          <template #loading>
            <span class="text-muted-foreground">{{ t("common.loading") }}</span>
          </template>
        </UTable>
        <div
          v-if="!selectedTrace && activeTab === 'runs'"
          class="flex justify-end border-t border-default px-3 py-2 sm:px-4"
        >
          <UPagination
            v-model:page="runsPage"
            :items-per-page="TRACE_PAGE_SIZE"
            :total="filteredTraceRuns.length"
            size="sm"
          />
        </div>
        <UTable
          v-if="!selectedTrace && activeTab === 'sessions'"
          :data="pagedTraceSessions"
          :columns="sessionColumns"
          :loading="loadingSessions || loadingTraceDetail"
          :empty="t('traces.emptySessions')"
          sticky="header"
          class="w-full min-w-0"
          :ui="tableUi"
          @select="selectSessionRow"
        >
          <template #loading>
            <span class="text-muted-foreground">{{ t("common.loading") }}</span>
          </template>
        </UTable>
        <div
          v-if="!selectedTrace && activeTab === 'sessions'"
          class="flex justify-end border-t border-default px-3 py-2 sm:px-4"
        >
          <UPagination
            v-model:page="sessionsPage"
            :items-per-page="TRACE_PAGE_SIZE"
            :total="filteredTraceSessions.length"
            size="sm"
          />
        </div>
      </div>
    </div>
  </div>
</template>
