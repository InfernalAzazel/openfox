<script setup lang="ts">
import type { TableColumn } from "@nuxt/ui"
import { computed, h, onMounted, ref, resolveComponent, watch } from "vue"
import { useI18n } from "vue-i18n"
import { z } from "zod"
import {
  deleteEvalRunsAPI,
  listEvalRunsAPI,
  runEvalAPI,
  type EvalRun,
  type EvalRunInput,
} from "@/api/evals"
import { getAgentsAPI } from "@/api/os"
import { getAgentOsBaseUrl } from "@/composables/request"
import { useAppState } from "@/composables/store"
import type { AgentDetails } from "@/types/os"

const { t, locale } = useI18n()
const toast = useToast()
const app = useAppState()

const UCheckbox = resolveComponent("UCheckbox")

/** 向导中仅三种类型，与参考 UI 一致；`agent_as_judge` 仅可能来自历史数据 */
type WizardEvalType = "accuracy" | "reliability" | "performance"

const EVAL_TABLE = "agno_eval_runs"

const fieldLabelClass =
  "text-[11px] font-semibold uppercase tracking-wide text-muted-foreground"

function firstZodMessage(error: z.ZodError): string {
  return error.issues[0]?.message ?? t("evals.validation.generic")
}

function getEvalWizardStep1Schema() {
  return z.object({
    wizardAgentId: z.string().trim().min(1, t("evals.validation.agentRequired")),
    newEvalType: z.enum(["accuracy", "reliability", "performance"]),
  })
}

function intAtLeast1(message: string) {
  return z.preprocess(
    (v) => Math.trunc(Number(v)),
    z.int().min(1, message),
  )
}

function intAtLeast0(message: string) {
  return z.preprocess(
    (v) => Math.trunc(Number(v)),
    z.int().min(0, message),
  )
}

function step2ModelKeySchema(hasModelOptions: boolean) {
  return hasModelOptions
    ? z.string().trim().min(1, t("evals.validation.modelRequired"))
    : z.string()
}

function getEvalWizardStep2AccuracySchema(hasModelOptions: boolean) {
  return z.object({
    input: z.string().trim().min(1, t("evals.inputRequired")),
    modelKey: step2ModelKeySchema(hasModelOptions),
    numIterations: intAtLeast1(t("evals.validation.iterationsMin")),
    expectedOutput: z
      .string()
      .trim()
      .min(1, t("evals.validation.expectedOutputRequired")),
  })
}

function getEvalWizardStep2ReliabilitySchema(hasModelOptions: boolean) {
  return z.object({
    input: z.string().trim().min(1, t("evals.inputRequired")),
    modelKey: step2ModelKeySchema(hasModelOptions),
    numIterations: intAtLeast1(t("evals.validation.iterationsMin")),
    expectedToolCalls: z
      .array(z.string())
      .min(1, t("evals.validation.expectedToolsRequired")),
  })
}

function getEvalWizardStep2PerformanceSchema(hasModelOptions: boolean) {
  return z.object({
    input: z.string().trim().min(1, t("evals.inputRequired")),
    modelKey: step2ModelKeySchema(hasModelOptions),
    numIterations: intAtLeast1(t("evals.validation.iterationsMin")),
    warmupRuns: intAtLeast0(t("evals.validation.warmupMin")),
  })
}

const agents = ref<AgentDetails[]>([])
const selectedAgentId = ref("")
const loadingAgents = ref(false)

const evalRuns = ref<EvalRun[]>([])
const loadingEvals = ref(false)
const pageError = ref<string | null>(null)

const rowSelection = ref<Record<string, boolean>>({})
const deleteConfirmOpen = ref(false)
const deleting = ref(false)

const newEvalOpen = ref(false)
const submittingEval = ref(false)
const newEvalWizardStep = ref<1 | 2>(1)
const wizardAgentId = ref("")
const newEvalType = ref<WizardEvalType>("accuracy")
const newEvalName = ref("")
const newEvalModelKey = ref("")
const newEvalNumIterations = ref(1)
const newEvalWarmupRuns = ref(0)
const newEvalInput = ref("")
const newEvalExpectedOutput = ref("")
const newEvalAdditionalGuidelines = ref("")
/** 可靠性评估：输入框草稿；确认后加入 `expectedToolCalls` */
const expectedToolCallDraft = ref("")
const expectedToolCalls = ref<string[]>([])
const isEvalProcessing = ref(false)
const accuracyResultsExpanded = ref(true)

const selectedAgent = computed(() =>
  agents.value.find((a) => a.id === selectedAgentId.value),
)

const evalsHeaderMeta = computed(() => {
  const fullId = selectedAgent.value?.db_id?.trim() || ""
  return {
    fullId: fullId || "—",
    table: EVAL_TABLE,
  }
})

const evalsDbIdEllipsis = computed(() => {
  const id = evalsHeaderMeta.value.fullId
  if (id === "—") return id
  const max = 28
  return id.length <= max ? id : `${id.slice(0, max)}...`
})

const hasOsAuth = computed(() => {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim()
  return !!(base && token)
})

function authHeaders() {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim()
  return { base, token }
}

const selectedIds = computed(() =>
  Object.keys(rowSelection.value).filter((k) => rowSelection.value[k]),
)
const selectedCount = computed(() => selectedIds.value.length)
const detailEvalRunId = ref("")
const EVALS_PAGE_SIZE = 5
const currentPage = ref(1)

const pagedEvalRuns = computed(() => {
  const start = (currentPage.value - 1) * EVALS_PAGE_SIZE
  return evalRuns.value.slice(start, start + EVALS_PAGE_SIZE)
})

const agentById = computed(() => {
  const m = new Map<string, AgentDetails>()
  for (const a of agents.value) {
    m.set(a.id, a)
  }
  return m
})

const wizardEvalTypeRadioItems = computed(() => [
  { value: "accuracy" as const, label: t("evals.typeAccuracy") },
  { value: "reliability" as const, label: t("evals.typeReliability") },
  { value: "performance" as const, label: t("evals.typePerformance") },
])

const agentSelectItemsForWizard = computed(() =>
  agents.value.map((a) => ({
    value: a.id,
    label: a.name?.trim() || a.id,
  })),
)

const wizardSelectedAgent = computed(() =>
  agents.value.find((a) => a.id === wizardAgentId.value),
)

const selectedEvalRun = computed(() =>
  evalRuns.value.find((r) => r.id === detailEvalRunId.value),
)

const wizardModelSelectItems = computed(() => {
  const m = wizardSelectedAgent.value?.model
  if (!m?.model?.trim() || !m.provider?.trim()) return []
  const prov = m.provider.trim()
  const mid = m.model.trim()
  return [
    {
      value: `${prov}::${mid}`,
      label: mid,
      description: prov,
    },
  ]
})

const wizardStepIndicator = computed(() =>
  t("evals.wizardStepOf", {
    current: newEvalWizardStep.value,
    total: 2,
  }),
)

const wizardSubtitle = computed(() => {
  if (newEvalWizardStep.value === 1) return t("evals.wizardStep1Hint")
  switch (newEvalType.value) {
    case "accuracy":
      return t("evals.wizardStep2HintAccuracy")
    case "reliability":
      return t("evals.wizardStep2HintReliability")
    case "performance":
      return t("evals.wizardStep2HintPerformance")
    default:
      return ""
  }
})

function parseModelKey(key: string): { model_id: string; model_provider: string } | null {
  const k = key.trim()
  if (!k) return null
  const i = k.indexOf("::")
  if (i <= 0) return null
  return {
    model_provider: k.slice(0, i).trim(),
    model_id: k.slice(i + 2).trim(),
  }
}

function syncModelKeyFromAgent() {
  const first = wizardModelSelectItems.value[0]
  newEvalModelKey.value = first?.value ?? ""
}

function resetWizardForm() {
  newEvalWizardStep.value = 1
  wizardAgentId.value = selectedAgentId.value
  newEvalType.value = "accuracy"
  newEvalName.value = ""
  newEvalNumIterations.value = 1
  newEvalWarmupRuns.value = 0
  newEvalInput.value = ""
  newEvalExpectedOutput.value = ""
  newEvalAdditionalGuidelines.value = ""
  expectedToolCallDraft.value = ""
  expectedToolCalls.value = []
  syncModelKeyFromAgent()
}

function formatDateTime(ts: string | null | undefined): string {
  if (!ts) return "—"
  try {
    const d = new Date(ts)
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

function formatEvalType(type: string): string {
  const map: Record<string, string> = {
    accuracy: t("evals.typeAccuracy"),
    agent_as_judge: t("evals.typeAgentAsJudge"),
    performance: t("evals.typePerformance"),
    reliability: t("evals.typeReliability"),
  }
  return map[type] ?? type
}

function displayName(row: EvalRun): string {
  const n = row.name?.trim()
  if (n) return n
  return row.id
}

function agentTeamCell(row: EvalRun) {
  if (row.team_id) {
    return h("div", { class: "flex min-w-0 items-center gap-2" }, [
      h("span", {
        class:
          "inline-flex size-6 shrink-0 items-center justify-center rounded-md bg-violet-600 text-white",
      }, [
        h(resolveComponent("UIcon"), { name: "i-lucide-users", class: "size-3" }),
      ]),
      h("span", { class: "min-w-0 truncate font-medium", title: row.team_id }, row.team_id),
    ])
  }
  const aid = row.agent_id?.trim() || ""
  const agent = aid ? agentById.value.get(aid) : undefined
  const label = agent?.name?.trim() || aid || "—"
  return h("div", { class: "flex min-w-0 items-center gap-2" }, [
    h("span", {
      class:
        "inline-flex size-6 shrink-0 items-center justify-center rounded-md bg-orange-500 text-white",
    }, [
      h(resolveComponent("UIcon"), { name: "i-lucide-scan-search", class: "size-3" }),
    ]),
    h("span", { class: "min-w-0 truncate font-medium", title: label }, label),
  ])
}

function modelCell(row: EvalRun) {
  const mid = row.model_id?.trim() || "—"
  const prov = row.model_provider?.trim()
  return h("div", { class: "flex min-w-0 items-center gap-2" }, [
    h("span", {
      class:
        "inline-flex size-6 shrink-0 items-center justify-center rounded-md bg-zinc-800 text-white dark:bg-zinc-200 dark:text-zinc-900",
    }, [
      h(resolveComponent("UIcon"), { name: "i-lucide-brain-circuit", class: "size-3" }),
    ]),
    h("div", { class: "min-w-0" }, [
      h("div", { class: "truncate font-mono text-sm", title: mid }, mid),
      prov
        ? h("div", { class: "truncate text-xs text-muted-foreground", title: prov }, prov)
        : null,
    ].filter(Boolean)),
  ])
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return null
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.map((v) => String(v)).filter(Boolean)
}

function formatUnknown(value: unknown): string {
  if (value == null) return "—"
  if (typeof value === "string") return value.trim() || "—"
  if (typeof value === "number" || typeof value === "boolean") return String(value)
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function formatScoreValue(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value.toFixed(2)
  }
  const asNum = Number(value)
  if (Number.isFinite(asNum)) return asNum.toFixed(2)
  return formatUnknown(value)
}

function formatDurationSeconds(value: unknown): string {
  if (value == null || value === "") return "—"
  if (typeof value === "number" && Number.isFinite(value)) {
    return `${value.toFixed(3)}s`
  }
  const text = String(value).trim()
  if (!text) return "—"
  if (/[a-zA-Z]+$/.test(text)) return text
  const asNum = Number(text)
  if (Number.isFinite(asNum)) return `${asNum.toFixed(3)}s`
  return text
}

function formatMemoryMib(value: unknown): string {
  if (value == null || value === "") return "—"
  if (typeof value === "number" && Number.isFinite(value)) {
    return value.toFixed(3)
  }
  const text = String(value).trim()
  if (!text) return "—"
  const asNum = Number(text)
  if (Number.isFinite(asNum)) return asNum.toFixed(3)
  return text
}

function getFirstDefined(...values: unknown[]): unknown {
  for (const v of values) {
    if (v !== undefined && v !== null && v !== "") return v
  }
  return undefined
}

function getByAlias(record: Record<string, unknown> | null, aliases: readonly string[]): unknown {
  if (!record) return undefined
  const normalizedAliases = aliases.map((a) => a.toLowerCase().replace(/[\s_-]+/g, ""))
  for (const [k, v] of Object.entries(record)) {
    const nk = k.toLowerCase().replace(/[\s_-]+/g, "")
    if (normalizedAliases.includes(nk)) return v
  }
  return undefined
}

function findFirstByKeysDeep(
  root: unknown,
  keys: string[],
): unknown {
  const keySet = new Set(keys.map((k) => k.toLowerCase()))
  const queue: unknown[] = [root]
  const seen = new Set<unknown>()

  while (queue.length) {
    const current = queue.shift()
    if (!current || typeof current !== "object") continue
    if (seen.has(current)) continue
    seen.add(current)

    if (Array.isArray(current)) {
      for (const item of current) queue.push(item)
      continue
    }

    const record = current as Record<string, unknown>
    for (const [k, v] of Object.entries(record)) {
      if (
        keySet.has(k.toLowerCase())
        && v !== undefined
        && v !== null
        && v !== ""
      ) {
        return v
      }
      if (typeof v === "object" && v) queue.push(v)
    }
  }
  return undefined
}

function onEvalRowSelect(event: Event, row: { original: EvalRun }) {
  const target = event.target as HTMLElement | null
  if (target?.closest("input,button,a")) return
  detailEvalRunId.value = row.original.id
}

function closeEvalDetail() {
  detailEvalRunId.value = ""
}

function deleteSelectedEvalFromDetail() {
  if (!selectedEvalRun.value) return
  rowSelection.value = { [selectedEvalRun.value.id]: true }
  openDeleteConfirm()
}

function rerunSelectedEvalFromDetail() {
  if (!selectedEvalRun.value) return
  const run = selectedEvalRun.value
  const input = asRecord(run.eval_input) ?? {}
  const data = asRecord(run.eval_data) ?? {}

  resetWizardForm()
  wizardAgentId.value = run.agent_id?.trim() || selectedAgentId.value

  if (
    run.eval_type === "accuracy"
    || run.eval_type === "reliability"
    || run.eval_type === "performance"
  ) {
    newEvalType.value = run.eval_type
  }

  newEvalName.value = run.name?.trim() ? `${run.name?.trim()} (rerun)` : ""
  newEvalInput.value = String(getFirstDefined(input.input, input.query, data.input, "") ?? "")
  newEvalNumIterations.value = Number(getFirstDefined(input.num_iterations, data.num_iterations, 1) ?? 1)

  if (newEvalType.value === "accuracy") {
    newEvalExpectedOutput.value = String(
      getFirstDefined(input.expected_output, data.expected_output, "") ?? "",
    )
  } else if (newEvalType.value === "reliability") {
    expectedToolCalls.value = asStringArray(
      getFirstDefined(input.expected_tool_calls, data.expected_tool_calls, []),
    )
  } else if (newEvalType.value === "performance") {
    newEvalWarmupRuns.value = Number(getFirstDefined(input.warmup_runs, data.warmup_runs, 0) ?? 0)
  }

  newEvalWizardStep.value = 2
  newEvalOpen.value = true
}

const selectedEvalData = computed<Record<string, unknown>>(() =>
  asRecord(selectedEvalRun.value?.eval_data) ?? {},
)
const selectedEvalInput = computed<Record<string, unknown>>(() =>
  asRecord(selectedEvalRun.value?.eval_input) ?? {},
)

const detailTitle = computed(() => {
  if (!selectedEvalRun.value) return ""
  const name = displayName(selectedEvalRun.value)
  const agent = selectedEvalRun.value.agent_id?.trim() || "—"
  const model = selectedEvalRun.value.model_id?.trim() || "—"
  return `${name} · ${agent} · ${model}`
})

const reliabilityDetailItems = computed(() => {
  const data = selectedEvalData.value
  return [
    { label: t("evals.detailEvalStatus"), value: formatUnknown(data.eval_status) },
    {
      label: t("evals.detailFailedToolCalls"),
      value: asStringArray(data.failed_tool_calls).join(", ") || "None",
    },
    {
      label: t("evals.detailPassedToolCalls"),
      value: asStringArray(data.passed_tool_calls).join(", ") || "None",
    },
  ]
})

const accuracyDetailItems = computed(() => {
  const data = selectedEvalData.value
  const input = selectedEvalInput.value
  const deepScore = findFirstByKeysDeep(data, [
    "score",
    "avg_score",
    "mean_score",
    "accuracy_score",
  ])
  const deepOutput = findFirstByKeysDeep(data, [
    "output",
    "agent_output",
    "response",
    "result_output",
  ])
  const deepExpectedOutput = getFirstDefined(
    findFirstByKeysDeep(input, ["expected_output", "ground_truth"]),
    findFirstByKeysDeep(data, ["expected_output", "ground_truth"]),
  )
  const deepInput = getFirstDefined(
    findFirstByKeysDeep(input, ["input", "query", "prompt"]),
    findFirstByKeysDeep(data, ["input", "query", "prompt"]),
  )
  const deepReason = findFirstByKeysDeep(data, [
    "reason",
    "explanation",
    "analysis",
    "rationale",
  ])

  return [
    {
      label: t("evals.detailScore"),
      value: formatUnknown(getFirstDefined(data.score, data.avg_score, data.mean_score, deepScore)),
    },
    {
      label: t("evals.detailOutput"),
      value: formatUnknown(getFirstDefined(data.output, data.agent_output, deepOutput)),
    },
    {
      label: t("evals.detailExpectedOutput"),
      value: formatUnknown(getFirstDefined(input.expected_output, data.expected_output, deepExpectedOutput)),
    },
    {
      label: t("evals.detailInput"),
      value: formatUnknown(getFirstDefined(input.input, data.input, deepInput)),
    },
    {
      label: t("evals.detailReason"),
      value: formatUnknown(getFirstDefined(data.reason, data.explanation, deepReason)),
    },
  ]
})

const accuracyScoreSummary = computed(() => {
  const data = selectedEvalData.value
  const items = [
    { label: t("evals.detailAvgScore"), value: getFirstDefined(data.avg_score) },
    {
      label: t("evals.detailMeanScore"),
      value: getFirstDefined(data.mean_score, data.avg_score),
    },
    { label: t("evals.detailMinScore"), value: getFirstDefined(data.min_score) },
    { label: t("evals.detailMaxScore"), value: getFirstDefined(data.max_score) },
    {
      label: t("evals.detailStdDevScore"),
      value: getFirstDefined(data.std_dev_score, data.std_score, data.stddev_score),
    },
  ]
  return items
    .filter((item) => item.value !== undefined && item.value !== null && item.value !== "")
    .map((item) => ({ label: item.label, value: formatScoreValue(item.value) }))
})

const performanceSummaryRows = computed(() => {
  const data = selectedEvalData.value
  const resultObj = asRecord(data.result)
  if (resultObj) {
    const rows = [
      {
        metric: "Average",
        time: getFirstDefined(resultObj.avg_run_time),
        memory: getFirstDefined(resultObj.avg_memory_usage),
      },
      {
        metric: "Minimum",
        time: getFirstDefined(resultObj.min_run_time),
        memory: getFirstDefined(resultObj.min_memory_usage),
      },
      {
        metric: "Maximum",
        time: getFirstDefined(resultObj.max_run_time),
        memory: getFirstDefined(resultObj.max_memory_usage),
      },
      {
        metric: "Standard deviation",
        time: getFirstDefined(resultObj.std_dev_run_time),
        memory: getFirstDefined(resultObj.std_dev_memory_usage),
      },
      {
        metric: "Median",
        time: getFirstDefined(resultObj.median_run_time),
        memory: getFirstDefined(resultObj.median_memory_usage),
      },
      {
        metric: "95th percentile",
        time: getFirstDefined(resultObj.p95_run_time),
        memory: getFirstDefined(resultObj.p95_memory_usage),
      },
    ].map((row) => ({
      metric: row.metric,
      time: formatDurationSeconds(row.time),
      memory: formatMemoryMib(row.memory),
    }))
    if (rows.some((r) => r.time !== "—" || r.memory !== "—")) return rows
  }

  const summaryRaw = getFirstDefined(data.summary, data.metrics)
  const summaryArray = Array.isArray(summaryRaw) ? summaryRaw : null
  if (summaryArray) {
    const rows = summaryArray.map((raw, idx) => {
      const row = asRecord(raw)
      return {
        metric: formatUnknown(getFirstDefined(row?.metric, row?.name, idx + 1)),
        time: formatDurationSeconds(getFirstDefined(row?.time, row?.duration, row?.time_s, row?.execution_time)),
        memory: formatMemoryMib(getFirstDefined(row?.memory_mb, row?.memory, row?.memory_mib)),
      }
    })
    return rows.filter((r) => r.time !== "—" || r.memory !== "—")
  }

  const summary = asRecord(summaryRaw)
  if (summary) {
    const rows = Object.entries(summary).map(([metric, raw]) => {
      const row = asRecord(raw)
      return {
        metric,
        time: formatDurationSeconds(getFirstDefined(row?.time, row?.duration, row?.time_s, row?.execution_time)),
        memory: formatMemoryMib(getFirstDefined(row?.memory_mb, row?.memory, row?.memory_mib)),
      }
    })
    if (rows.some((r) => r.time !== "—" || r.memory !== "—")) return rows
  }

  const timeStats = asRecord(getFirstDefined(
    data.time_stats,
    data.duration_stats,
    data.latency_stats,
    data.time,
    data.duration,
  ))
  const memoryStats = asRecord(getFirstDefined(data.memory_stats, data.mem_stats, data.memory))

  const metricDefs = [
    { label: "Average", aliases: ["average", "avg", "mean"] },
    { label: "Minimum", aliases: ["minimum", "min"] },
    { label: "Maximum", aliases: ["maximum", "max"] },
    { label: "Standard deviation", aliases: ["standard_deviation", "std_dev", "std", "stddev"] },
    { label: "Median", aliases: ["median"] },
    { label: "95th percentile", aliases: ["95th_percentile", "95_percentile", "p95", "percentile_95"] },
  ] as const

  const rows = metricDefs.map((m) => {
    const raw = getFirstDefined(
      getByAlias(data, m.aliases),
      getByAlias(timeStats, m.aliases),
      getByAlias(memoryStats, m.aliases),
    )
    const rawObj = asRecord(raw)
    const time = formatUnknown(getFirstDefined(
      rawObj?.time,
      rawObj?.duration,
      rawObj?.time_s,
      rawObj?.execution_time,
      getByAlias(timeStats, m.aliases),
      typeof raw === "number" || typeof raw === "string" ? raw : undefined,
    ))
    const memory = formatMemoryMib(getFirstDefined(
      rawObj?.memory_mb,
      rawObj?.memory,
      rawObj?.memory_mib,
      getByAlias(memoryStats, m.aliases),
    ))
    return { metric: m.label, time: formatDurationSeconds(time), memory }
  })

  return rows.filter((r) => r.time !== "—" || r.memory !== "—")
})

const performanceRunRows = computed(() => {
  const data = selectedEvalData.value
  const runsRaw = getFirstDefined(
    data.result && asRecord(data.result)?.runs,
    data.individual_runs,
    data.runs,
    data.run_metrics,
    data.individual_run_metrics,
  )
  if (!Array.isArray(runsRaw)) return [] as Array<{ run: string; time: string; memory: string }>
  return runsRaw.map((raw, idx) => {
    const row = asRecord(raw)
    return {
      run: formatUnknown(getFirstDefined(row?.run, row?.id, idx + 1)),
      time: formatDurationSeconds(getFirstDefined(
        row?.runtime,
        row?.run_time,
        row?.time,
        row?.duration,
        row?.time_s,
        row?.execution_time,
        row?.latency,
      )),
      memory: formatMemoryMib(getFirstDefined(row?.memory_mb, row?.memory, row?.memory_mib)),
    }
  })
})

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

async function refreshEvalRuns() {
  const { base, token } = authHeaders()
  const agentId = selectedAgentId.value
  const dbId = selectedAgent.value?.db_id
  if (!base || !token || !agentId) {
    evalRuns.value = []
    rowSelection.value = {}
    return
  }
  loadingEvals.value = true
  pageError.value = null
  try {
    const res = await listEvalRunsAPI(base, token, {
      agent_id: agentId,
      db_id: dbId || undefined,
      table: EVAL_TABLE,
      limit: 100,
      sort_by: "updated_at",
      sort_order: "desc",
    })
    if (!res.ok) {
      pageError.value = t("evals.loadFailed", { message: res.message })
      evalRuns.value = []
      rowSelection.value = {}
      return
    }
    evalRuns.value = res.data.data
    const alive = new Set(res.data.data.map((r) => r.id))
    const next = { ...rowSelection.value }
    for (const k of Object.keys(next)) {
      if (!alive.has(k)) delete next[k]
    }
    rowSelection.value = next
  } finally {
    loadingEvals.value = false
  }
}

async function refreshAll() {
  await refreshAgents()
  await refreshEvalRuns()
}

function clearSelection() {
  rowSelection.value = {}
  deleteConfirmOpen.value = false
}

function openDeleteConfirm() {
  if (!selectedIds.value.length || deleting.value) return
  deleteConfirmOpen.value = true
}

async function confirmDeleteEvalRuns() {
  if (!selectedIds.value.length || deleting.value) return
  const { base, token } = authHeaders()
  const dbId = selectedAgent.value?.db_id
  if (!base || !token) return
  deleting.value = true
  try {
    const res = await deleteEvalRunsAPI(base, token, [...selectedIds.value], {
      db_id: dbId || undefined,
      table: EVAL_TABLE,
    })
    if (!res.ok) {
      toast.add({ title: t("evals.deleteFailed", { message: res.message }), color: "error" })
      return
    }
    rowSelection.value = {}
    deleteConfirmOpen.value = false
    toast.add({ title: t("evals.deleted"), color: "success" })
    await refreshEvalRuns()
  } finally {
    deleting.value = false
  }
}

function openNewEval() {
  resetWizardForm()
  newEvalOpen.value = true
}

function goWizardNext() {
  if (newEvalWizardStep.value !== 1) return
  const step1 = getEvalWizardStep1Schema().safeParse({
    wizardAgentId: wizardAgentId.value,
    newEvalType: newEvalType.value,
  })
  if (!step1.success) {
    toast.add({ title: firstZodMessage(step1.error), color: "warning" })
    return
  }
  newEvalWizardStep.value = 2
  syncModelKeyFromAgent()
}

function goWizardBack() {
  if (newEvalWizardStep.value !== 2) return
  newEvalWizardStep.value = 1
}

function addExpectedToolCallFromDraft() {
  const s = expectedToolCallDraft.value.trim()
  if (!s) return
  if (!expectedToolCalls.value.includes(s)) {
    expectedToolCalls.value = [...expectedToolCalls.value, s]
  }
  expectedToolCallDraft.value = ""
}

function removeExpectedToolCallAt(index: number) {
  expectedToolCalls.value = expectedToolCalls.value.filter((_, i) => i !== index)
}

async function submitNewEval() {
  const { base, token } = authHeaders()
  const agentId = wizardAgentId.value.trim()
  const dbId = wizardSelectedAgent.value?.db_id
  if (!base || !token || !agentId) {
    toast.add({ title: t("evals.needAgent"), color: "warning" })
    return
  }

  const hasModel = wizardModelSelectItems.value.length > 0
  const runName = newEvalName.value.trim() || undefined
  const guidelines = newEvalAdditionalGuidelines.value.trim() || undefined

  function applyModelAndGuidelines(b: EvalRunInput, modelKey: string) {
    const modelParts = parseModelKey(modelKey)
    if (modelParts?.model_id && modelParts.model_provider) {
      b.model_id = modelParts.model_id
      b.model_provider = modelParts.model_provider
    }
    if (guidelines) b.additional_guidelines = guidelines
  }

  let body: EvalRunInput

  if (newEvalType.value === "accuracy") {
    const r = getEvalWizardStep2AccuracySchema(hasModel).safeParse({
      input: newEvalInput.value,
      modelKey: newEvalModelKey.value,
      numIterations: newEvalNumIterations.value,
      expectedOutput: newEvalExpectedOutput.value,
    })
    if (!r.success) {
      toast.add({ title: firstZodMessage(r.error), color: "warning" })
      return
    }
    body = {
      agent_id: agentId,
      eval_type: "accuracy",
      input: r.data.input,
      name: runName,
      num_iterations: r.data.numIterations,
      expected_output: r.data.expectedOutput,
    }
    applyModelAndGuidelines(body, r.data.modelKey)
  } else if (newEvalType.value === "reliability") {
    const r = getEvalWizardStep2ReliabilitySchema(hasModel).safeParse({
      input: newEvalInput.value,
      modelKey: newEvalModelKey.value,
      numIterations: newEvalNumIterations.value,
      expectedToolCalls: expectedToolCalls.value,
    })
    if (!r.success) {
      toast.add({ title: firstZodMessage(r.error), color: "warning" })
      return
    }
    body = {
      agent_id: agentId,
      eval_type: "reliability",
      input: r.data.input,
      name: runName,
      num_iterations: r.data.numIterations,
      expected_tool_calls: [...r.data.expectedToolCalls],
    }
    applyModelAndGuidelines(body, r.data.modelKey)
  } else {
    const r = getEvalWizardStep2PerformanceSchema(hasModel).safeParse({
      input: newEvalInput.value,
      modelKey: newEvalModelKey.value,
      numIterations: newEvalNumIterations.value,
      warmupRuns: newEvalWarmupRuns.value,
    })
    if (!r.success) {
      toast.add({ title: firstZodMessage(r.error), color: "warning" })
      return
    }
    body = {
      agent_id: agentId,
      eval_type: "performance",
      input: r.data.input,
      name: runName,
      num_iterations: r.data.numIterations,
      warmup_runs: r.data.warmupRuns,
    }
    applyModelAndGuidelines(body, r.data.modelKey)
  }

  // 提交后立即关闭弹窗，避免接口耗时导致按钮长期 loading 卡住
  newEvalOpen.value = false
  submittingEval.value = true
  isEvalProcessing.value = true
  try {
    const res = await runEvalAPI(base, token, body, {
      db_id: dbId || undefined,
      table: EVAL_TABLE,
    })
    if (!res.ok) {
      isEvalProcessing.value = false
      toast.add({ title: t("evals.runFailed", { message: res.message }), color: "error" })
      return
    }
    toast.add({ title: t("evals.runSuccess"), color: "success" })
    await refreshEvalRuns()
  } finally {
    isEvalProcessing.value = false
    submittingEval.value = false
  }
}

const columns = computed<TableColumn<EvalRun>[]>(() => [
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
        "aria-label": t("evals.selectAll"),
      }),
    cell: ({ row }) =>
      h(UCheckbox, {
        "modelValue": row.getIsSelected(),
        "onUpdate:modelValue": (value: boolean | "indeterminate") =>
          row.toggleSelected(!!value),
        "aria-label": t("evals.selectRow", {
          name: displayName(row.original),
        }),
      }),
    enableSorting: false,
    enableHiding: false,
  },
  {
    accessorKey: "name",
    header: t("evals.colName"),
    meta: {
      class: {
        th: "min-w-0 w-[18%]",
        td: "max-w-0 min-w-0",
      },
    },
    cell: ({ row }) =>
      h(
        "span",
        {
          class: "block min-w-0 truncate text-sm font-medium text-foreground",
          title: displayName(row.original),
        },
        displayName(row.original),
      ),
  },
  {
    id: "agent_team",
    header: t("evals.colAgentTeam"),
    meta: {
      class: {
        th: "min-w-0 w-[22%]",
        td: "max-w-0 min-w-0",
      },
    },
    cell: ({ row }) => agentTeamCell(row.original),
  },
  {
    id: "model",
    header: t("evals.colModel"),
    meta: {
      class: {
        th: "min-w-0 w-[26%]",
        td: "max-w-0 min-w-0",
      },
    },
    cell: ({ row }) => modelCell(row.original),
  },
  {
    accessorKey: "eval_type",
    header: t("evals.colType"),
    meta: {
      class: {
        th: "w-[14%]",
        td: "text-sm text-muted-foreground",
      },
    },
    cell: ({ row }) => formatEvalType(row.original.eval_type),
  },
  {
    id: "updated_at",
    accessorFn: (row) => row.updated_at ?? "",
    header: t("evals.colUpdatedAt"),
    cell: ({ row }) => formatDateTime(row.original.updated_at),
    meta: {
      class: {
        th: "text-right w-[20%]",
        td: "text-right text-sm whitespace-nowrap tabular-nums text-muted-foreground",
      },
    },
  },
])

const tableUi = {
  root: "overflow-x-auto",
  base: "min-w-full table-fixed",
  thead: "bg-elevated/40",
  th: "border-b border-default py-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground",
  tbody: "divide-y divide-default",
  tr: "odd:bg-default even:bg-elevated/30 hover:bg-elevated/45 dark:even:bg-white/[0.06]",
  td: "py-2.5 px-3 text-sm align-middle",
  separator: "hidden",
  empty: "py-8 text-sm text-muted-foreground",
  loading: "py-8 text-sm",
}

const tableMeta = computed(() => ({
  class: {
    tr: (row: { original?: EvalRun } | null) => {
      const id = row?.original?.id
      if (id && id === detailEvalRunId.value) {
        return "!bg-primary/12 hover:!bg-primary/14 dark:!bg-primary/24"
      }
      return ""
    },
  },
}))

onMounted(() => {
  if (hasOsAuth.value) {
    void refreshAll()
  }
})

watch(
  () => [selectedAgentId.value, app.value.access_token] as const,
  () => {
    rowSelection.value = {}
    deleteConfirmOpen.value = false
    if (hasOsAuth.value) {
      void refreshEvalRuns()
    }
  },
)

watch(selectedCount, (n) => {
  if (n === 0) deleteConfirmOpen.value = false
})

watch(
  () => evalRuns.value.length,
  (len) => {
    const maxPage = Math.max(1, Math.ceil(len / EVALS_PAGE_SIZE))
    if (currentPage.value > maxPage) currentPage.value = maxPage
  },
)

watch(evalRuns, (rows) => {
  if (!detailEvalRunId.value) return
  if (!rows.some((r) => r.id === detailEvalRunId.value)) {
    detailEvalRunId.value = ""
  }
})

watch(detailEvalRunId, () => {
  accuracyResultsExpanded.value = true
})

watch(newEvalOpen, (open) => {
  if (!open) {
    newEvalWizardStep.value = 1
  }
})

watch(
  () => wizardAgentId.value,
  () => {
    if (newEvalWizardStep.value === 2) syncModelKeyFromAgent()
  },
)

watch(
  () => [selectedAgentId.value, app.value.access_token] as const,
  () => {
    currentPage.value = 1
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
            :title="evalsHeaderMeta.fullId !== '—' ? evalsHeaderMeta.fullId : undefined"
          >
            {{ evalsDbIdEllipsis }}
          </span>
          <span class="col-start-2 row-start-2 font-mono text-sm leading-snug font-medium whitespace-nowrap">
            {{ evalsHeaderMeta.table }}
          </span>
        </div>
      </div>

      <UAlert
        v-if="pageError && hasOsAuth"
        color="error"
        variant="subtle"
        class="shrink-0"
        :description="pageError"
      />

      <UAlert
        v-if="!hasOsAuth"
        color="warning"
        variant="subtle"
        class="rounded-lg border-dashed"
        :description="t('evals.needLogin')"
      />

      <div
        v-else
        :class="selectedEvalRun
          ? 'grid min-h-0 items-start gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(26rem,36rem)]'
          : ''"
      >
        <div class="overflow-hidden rounded-lg border border-default bg-default shadow-sm">
          <div
            class="flex min-h-12 flex-nowrap items-center justify-between gap-3 overflow-x-auto border-b border-default px-3 py-3 sm:min-h-14 sm:px-4 sm:py-3.5"
          >
            <div class="flex min-w-0 flex-1 items-center gap-3">
              <span class="shrink-0 text-xs text-muted-foreground">
                {{
                  loadingEvals
                    ? t("common.loading")
                    : t("common.itemsInTable", { count: evalRuns.length })
                }}
              </span>
              <UBadge
                v-if="isEvalProcessing"
                color="warning"
                variant="soft"
                class="inline-flex items-center gap-1.5 text-xs font-medium"
              >
                <UIcon name="i-lucide-loader-circle" class="size-3.5 animate-spin" />
                {{ t("evals.running") }}
              </UBadge>
            </div>
            <div class="flex shrink-0 items-center gap-2 sm:gap-3">
              <template v-if="selectedCount === 0">
                <UButton
                  v-if="!isEvalProcessing"
                  color="primary"
                  variant="solid"
                  size="sm"
                  icon="i-lucide-plus"
                  :disabled="!selectedAgentId"
                  @click="openNewEval"
                >
                  {{ t("evals.newEval") }}
                </UButton>
                <UButton
                  color="neutral"
                  variant="outline"
                  size="sm"
                  square
                  icon="i-lucide-refresh-cw"
                  :aria-label="t('common.refresh')"
                  :title="t('common.refresh')"
                  :disabled="loadingAgents || loadingEvals"
                  :loading="loadingAgents || loadingEvals"
                  class="shrink-0"
                  @click="void refreshAll()"
                />
              </template>
              <template v-if="selectedCount > 0 && !deleteConfirmOpen">
                <span
                  class="shrink-0 text-xs tabular-nums text-muted-foreground"
                  role="status"
                  aria-live="polite"
                >
                  {{ t("evals.selectedCount", { count: selectedCount }) }}
                </span>
                <UButton
                  variant="outline"
                  color="neutral"
                  size="sm"
                  class="shrink-0"
                  :disabled="deleting"
                  @click="clearSelection"
                >
                  {{ t("common.cancel") }}
                </UButton>
                <UButton
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
            v-model:row-selection="rowSelection"
            :data="pagedEvalRuns"
            :columns="columns"
            :loading="loadingEvals"
            :get-row-id="(row: EvalRun) => row.id"
            :empty="t('evals.empty')"
            :on-select="onEvalRowSelect"
          :meta="tableMeta"
            sticky="header"
            class="w-full min-w-0"
            :ui="tableUi"
          >
            <template #loading>
              <span class="text-muted-foreground">{{ t("common.loading") }}</span>
            </template>
          </UTable>
          <div class="flex justify-end border-t border-default px-3 py-2 sm:px-4">
            <UPagination
              v-model:page="currentPage"
              :items-per-page="EVALS_PAGE_SIZE"
              :total="evalRuns.length"
              size="sm"
            />
          </div>
        </div>

        <aside
          v-if="selectedEvalRun"
          class="flex min-h-0 max-h-[calc(100vh-9rem)] flex-col overflow-hidden rounded-lg border border-default bg-default shadow-sm"
        >
          <header class="flex items-start justify-between gap-3 border-b border-default px-4 py-3">
            <div class="min-w-0">
              <p class="truncate text-sm font-semibold text-foreground" :title="detailTitle">
                {{ detailTitle }}
              </p>
              <p class="mt-1 text-xs text-muted-foreground">
                {{ formatEvalType(selectedEvalRun.eval_type) }}
              </p>
            </div>
            <UButton
              color="neutral"
              variant="ghost"
              size="sm"
              square
              icon="i-lucide-x"
              :aria-label="t('evals.closeDetail')"
              @click="closeEvalDetail"
            />
          </header>

          <div class="min-h-0 flex-1 overflow-auto p-4">
            <div v-if="selectedEvalRun.eval_type === 'performance'" class="space-y-5">
              <table class="w-full table-fixed border-collapse text-sm">
                <thead class="bg-elevated/50 text-xs tracking-wide text-muted-foreground">
                  <tr>
                    <th class="border border-default px-2 py-1.5 text-left">{{ t("evals.detailMetric") }}</th>
                    <th class="border border-default px-2 py-1.5 text-right">{{ t("evals.detailTime") }}</th>
                    <th class="border border-default px-2 py-1.5 text-right">{{ t("evals.detailMemoryMB") }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in performanceSummaryRows" :key="row.metric">
                    <td class="border border-default px-2 py-1.5">{{ row.metric }}</td>
                    <td class="border border-default px-2 py-1.5 text-right tabular-nums">{{ row.time }}</td>
                    <td class="border border-default px-2 py-1.5 text-right tabular-nums">{{ row.memory }}</td>
                  </tr>
                </tbody>
              </table>

              <div v-if="performanceRunRows.length" class="space-y-2">
                <p class="text-sm font-semibold">{{ t("evals.detailIndividualRuns") }}</p>
                <table class="w-full table-fixed border-collapse text-sm">
                  <thead class="bg-elevated/50 text-xs tracking-wide text-muted-foreground">
                    <tr>
                      <th class="border border-default px-2 py-1.5 text-left">{{ t("evals.detailRun") }}</th>
                      <th class="border border-default px-2 py-1.5 text-right">{{ t("evals.detailTime") }}</th>
                      <th class="border border-default px-2 py-1.5 text-right">{{ t("evals.detailMemoryMB") }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in performanceRunRows" :key="row.run">
                      <td class="border border-default px-2 py-1.5">{{ row.run }}</td>
                      <td class="border border-default px-2 py-1.5 text-right tabular-nums">{{ row.time }}</td>
                      <td class="border border-default px-2 py-1.5 text-right tabular-nums">{{ row.memory }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div v-else-if="selectedEvalRun.eval_type === 'reliability'" class="space-y-2">
              <div
                v-for="item in reliabilityDetailItems"
                :key="item.label"
                class="rounded-md border border-default px-3 py-2"
              >
                <p class="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {{ item.label }}
                </p>
                <p class="mt-1 text-sm text-foreground">{{ item.value }}</p>
              </div>
            </div>

            <div v-else class="space-y-4">
              <div
                v-if="accuracyScoreSummary.length"
                class="grid gap-0 overflow-hidden rounded-xl border border-default sm:grid-cols-5"
              >
                <div
                  v-for="item in accuracyScoreSummary"
                  :key="item.label"
                  class="border-b border-default px-3 py-2 text-center last:border-b-0 sm:border-r sm:last:border-r-0"
                >
                  <p class="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {{ item.label }}
                  </p>
                  <p class="mt-2 text-2xl font-semibold tabular-nums text-foreground">
                    {{ item.value }}
                  </p>
                </div>
              </div>

              <section class="overflow-hidden rounded-xl border border-default">
                <header class="flex items-center justify-between border-b border-default px-4 py-3">
                  <p class="text-3.5 font-semibold">{{ t("evals.detailResults") }}</p>
                  <UButton
                    color="neutral"
                    variant="ghost"
                    size="sm"
                    square
                    :icon="accuracyResultsExpanded ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
                    :aria-label="t('evals.detailResults')"
                    @click="accuracyResultsExpanded = !accuracyResultsExpanded"
                  />
                </header>

                <div v-if="accuracyResultsExpanded" class="max-h-[52vh] overflow-y-auto px-4">
                  <div
                    v-for="(item, idx) in accuracyDetailItems"
                    :key="item.label"
                    class="grid grid-cols-[8rem_minmax(0,1fr)] gap-3 py-4"
                    :class="idx !== accuracyDetailItems.length - 1 ? 'border-b border-default' : ''"
                  >
                    <p class="text-lg font-semibold text-foreground">
                      {{ item.label }}
                    </p>
                    <p class="text-base whitespace-pre-wrap text-foreground">
                      {{ item.value }}
                    </p>
                  </div>
                </div>
              </section>
            </div>
          </div>

          <footer class="sticky bottom-0 z-10 flex items-center gap-2 border-t border-default bg-default px-4 py-3">
            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              @click="deleteSelectedEvalFromDetail"
            >
              {{ t("common.delete") }}
            </UButton>
            <UButton
              color="primary"
              variant="solid"
              size="sm"
              @click="rerunSelectedEvalFromDetail"
            >
              {{ t("evals.detailRerun") }}
            </UButton>
          </footer>
        </aside>
      </div>

      <UModal
        v-model:open="deleteConfirmOpen"
        :title="t('evals.deleteTitle', { count: selectedCount })"
        :description="t('evals.deleteHint')"
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
              @click="void confirmDeleteEvalRuns()"
            >
              {{ deleting ? t("evals.deleting") : t("common.delete") }}
            </UButton>
          </div>
        </template>
      </UModal>

      <UModal
        v-model:open="newEvalOpen"
        scrollable
        class="sm:max-w-2xl"
      >
        <template #title>
          <div class="flex w-full items-start justify-between gap-3 pr-8">
            <span class="text-base font-semibold leading-snug">
              {{ t("evals.wizardTitle") }}
            </span>
            <span
              class="shrink-0 pt-0.5 text-xs font-normal tabular-nums text-muted-foreground"
            >
              {{ wizardStepIndicator }}
            </span>
          </div>
        </template>
        <template #description>
          <p class="text-sm text-muted-foreground">
            {{ wizardSubtitle }}
          </p>
        </template>
        <template #body>
          <div v-if="newEvalWizardStep === 1" class="space-y-6">
            <div class="space-y-2">
              <p :class="fieldLabelClass">
                {{ t("evals.wizardSelectAgentTeam") }}
              </p>
              <USelect
                v-model="wizardAgentId"
                :items="agentSelectItemsForWizard"
                value-key="value"
                label-key="label"
                leading
                leading-icon="i-lucide-scan-search"
                :disabled="loadingAgents || !agents.length"
                :placeholder="t('evals.wizardAgentPlaceholder')"
                class="w-full"
              />
            </div>
            <div class="space-y-2">
              <p :class="fieldLabelClass">
                {{ t("evals.wizardChooseEvalType") }}
              </p>
              <URadioGroup
                v-model="newEvalType"
                :items="wizardEvalTypeRadioItems"
                value-key="value"
                label-key="label"
                orientation="vertical"
                variant="list"
              />
            </div>
          </div>

          <div v-else class="space-y-5">
            <div
              v-if="newEvalType === 'accuracy'"
              class="grid gap-4 sm:grid-cols-3"
            >
              <div class="space-y-2 sm:col-span-1">
                <p :class="fieldLabelClass">{{ t("evals.formRunName") }}</p>
                <UInput
                  v-model="newEvalName"
                  :placeholder="t('evals.formRunNamePlaceholder')"
                  class="w-full"
                />
              </div>
              <div class="space-y-2 sm:col-span-1">
                <p :class="fieldLabelClass">{{ t("evals.formEvalModel") }}</p>
                <USelect
                  v-model="newEvalModelKey"
                  :items="wizardModelSelectItems"
                  value-key="value"
                  label-key="label"
                  description-key="description"
                  leading
                  leading-icon="i-lucide-brain-circuit"
                  :disabled="!wizardModelSelectItems.length"
                  class="w-full"
                />
              </div>
              <div class="space-y-2 sm:col-span-1">
                <div class="flex items-center gap-1.5">
                  <p :class="fieldLabelClass">
                    {{ t("evals.formNumIterations") }}
                  </p>
                  <UTooltip :text="t('evals.tooltipIterations')">
                    <button
                      type="button"
                      class="inline-flex rounded-sm text-muted-foreground hover:text-foreground"
                    >
                      <UIcon
                        name="i-lucide-info"
                        class="size-3.5 shrink-0"
                      />
                    </button>
                  </UTooltip>
                </div>
                <UInput
                  v-model.number="newEvalNumIterations"
                  type="number"
                  min="1"
                  class="w-full"
                />
              </div>
            </div>

            <div
              v-else-if="newEvalType === 'reliability'"
              class="grid gap-4 sm:grid-cols-3"
            >
              <div class="space-y-2 sm:col-span-1">
                <p :class="fieldLabelClass">{{ t("evals.formRunName") }}</p>
                <UInput
                  v-model="newEvalName"
                  :placeholder="t('evals.formRunNamePlaceholder')"
                  class="w-full"
                />
              </div>
              <div class="space-y-2 sm:col-span-1">
                <p :class="fieldLabelClass">{{ t("evals.formEvalModel") }}</p>
                <USelect
                  v-model="newEvalModelKey"
                  :items="wizardModelSelectItems"
                  value-key="value"
                  label-key="label"
                  description-key="description"
                  leading
                  leading-icon="i-lucide-brain-circuit"
                  :disabled="!wizardModelSelectItems.length"
                  class="w-full"
                />
              </div>
              <div class="space-y-2 sm:col-span-1">
                <div class="flex items-center gap-1.5">
                  <p :class="fieldLabelClass">
                    {{ t("evals.formNumIterations") }}
                  </p>
                  <UTooltip :text="t('evals.tooltipIterations')">
                    <button
                      type="button"
                      class="inline-flex rounded-sm text-muted-foreground hover:text-foreground"
                    >
                      <UIcon
                        name="i-lucide-info"
                        class="size-3.5 shrink-0"
                      />
                    </button>
                  </UTooltip>
                </div>
                <UInput
                  v-model.number="newEvalNumIterations"
                  type="number"
                  min="1"
                  class="w-full"
                />
              </div>
            </div>

            <div
              v-else-if="newEvalType === 'performance'"
              class="space-y-4"
            >
              <div class="grid gap-4 sm:grid-cols-2">
                <div class="space-y-2">
                  <p :class="fieldLabelClass">{{ t("evals.formRunName") }}</p>
                  <UInput
                    v-model="newEvalName"
                    :placeholder="t('evals.formRunNamePlaceholder')"
                    class="w-full"
                  />
                </div>
                <div class="space-y-2">
                  <p :class="fieldLabelClass">{{ t("evals.formEvalModel") }}</p>
                  <USelect
                    v-model="newEvalModelKey"
                    :items="wizardModelSelectItems"
                    value-key="value"
                    label-key="label"
                    description-key="description"
                    leading
                    leading-icon="i-lucide-brain-circuit"
                    :disabled="!wizardModelSelectItems.length"
                    class="w-full"
                  />
                </div>
              </div>
              <div class="grid gap-4 sm:grid-cols-2">
                <div class="space-y-2">
                  <div class="flex items-center gap-1.5">
                    <p :class="fieldLabelClass">
                      {{ t("evals.formWarmupRuns") }}
                    </p>
                    <UTooltip :text="t('evals.tooltipWarmupRuns')">
                      <button
                        type="button"
                        class="inline-flex rounded-sm text-muted-foreground hover:text-foreground"
                      >
                        <UIcon
                          name="i-lucide-info"
                          class="size-3.5 shrink-0"
                        />
                      </button>
                    </UTooltip>
                  </div>
                  <UInput
                    v-model.number="newEvalWarmupRuns"
                    type="number"
                    min="0"
                    class="w-full"
                  />
                </div>
                <div class="space-y-2">
                  <div class="flex items-center gap-1.5">
                    <p :class="fieldLabelClass">
                      {{ t("evals.formNumIterations") }}
                    </p>
                    <UTooltip :text="t('evals.tooltipIterations')">
                      <button
                        type="button"
                        class="inline-flex rounded-sm text-muted-foreground hover:text-foreground"
                      >
                        <UIcon
                          name="i-lucide-info"
                          class="size-3.5 shrink-0"
                        />
                      </button>
                    </UTooltip>
                  </div>
                  <UInput
                    v-model.number="newEvalNumIterations"
                    type="number"
                    min="1"
                    class="w-full"
                  />
                </div>
              </div>
            </div>

            <div class="space-y-2">
              <div class="flex items-center gap-1.5">
                <p :class="fieldLabelClass">{{ t("evals.formInput") }}</p>
                <UTooltip :text="t('evals.tooltipInput')">
                  <button
                    type="button"
                    class="inline-flex rounded-sm text-muted-foreground hover:text-foreground"
                  >
                    <UIcon name="i-lucide-info" class="size-3.5 shrink-0" />
                  </button>
                </UTooltip>
              </div>
              <UTextarea
                v-model="newEvalInput"
                :rows="4"
                autoresize
                :placeholder="t('evals.formInputPlaceholder')"
                class="w-full"
              />
            </div>

            <template v-if="newEvalType === 'accuracy'">
              <div class="space-y-2">
                <div class="flex items-center gap-1.5">
                  <p :class="fieldLabelClass">
                    {{ t("evals.formExpectedOutput") }}
                  </p>
                  <UTooltip :text="t('evals.tooltipExpectedOutput')">
                    <button
                      type="button"
                      class="inline-flex rounded-sm text-muted-foreground hover:text-foreground"
                    >
                      <UIcon
                        name="i-lucide-info"
                        class="size-3.5 shrink-0"
                      />
                    </button>
                  </UTooltip>
                </div>
                <UTextarea
                  v-model="newEvalExpectedOutput"
                  :rows="3"
                  autoresize
                  :placeholder="t('evals.formExpectedOutputPlaceholder')"
                  class="w-full"
                />
              </div>
              <div class="space-y-2">
                <div class="flex items-center gap-1.5">
                  <p :class="fieldLabelClass">
                    {{ t("evals.formGuidelinesOptional") }}
                  </p>
                  <UTooltip :text="t('evals.tooltipGuidelines')">
                    <button
                      type="button"
                      class="inline-flex rounded-sm text-muted-foreground hover:text-foreground"
                    >
                      <UIcon
                        name="i-lucide-info"
                        class="size-3.5 shrink-0"
                      />
                    </button>
                  </UTooltip>
                </div>
                <UTextarea
                  v-model="newEvalAdditionalGuidelines"
                  :rows="2"
                  autoresize
                  :placeholder="t('evals.formGuidelinesPlaceholder')"
                  class="w-full"
                />
              </div>
            </template>

            <template v-else-if="newEvalType === 'reliability'">
              <div class="space-y-2">
                <div class="flex items-center gap-1.5">
                  <p :class="fieldLabelClass">
                    {{ t("evals.formExpectedToolCalls") }}
                  </p>
                  <UTooltip :text="t('evals.tooltipExpectedTools')">
                    <button
                      type="button"
                      class="inline-flex rounded-sm text-muted-foreground hover:text-foreground"
                    >
                      <UIcon
                        name="i-lucide-info"
                        class="size-3.5 shrink-0"
                      />
                    </button>
                  </UTooltip>
                </div>
                <div class="space-y-2">
                  <div class="flex items-center gap-2">
                    <UInput
                      v-model="expectedToolCallDraft"
                      :placeholder="t('evals.formExpectedToolCallsPlaceholder')"
                      class="min-w-0 flex-1"
                      @keydown.enter.prevent="addExpectedToolCallFromDraft"
                    />
                    <UButton
                      color="neutral"
                      variant="outline"
                      square
                      size="sm"
                      icon="i-lucide-plus"
                      type="button"
                      class="shrink-0"
                      :aria-label="t('evals.formAddToolCall')"
                      @click="addExpectedToolCallFromDraft"
                    />
                  </div>
                  <div
                    v-if="expectedToolCalls.length"
                    class="flex flex-wrap gap-1.5"
                  >
                    <UBadge
                      v-for="(tool, idx) in expectedToolCalls"
                      :key="`${idx}-${tool}`"
                      color="neutral"
                      variant="subtle"
                      class="max-w-full gap-1 pr-1"
                    >
                      <span class="min-w-0 truncate" :title="tool">{{ tool }}</span>
                      <UButton
                        color="neutral"
                        variant="link"
                        size="2xs"
                        square
                        icon="i-lucide-x"
                        type="button"
                        class="size-4 shrink-0"
                        :aria-label="t('evals.formRemoveToolCallChip', { name: tool })"
                        @click="removeExpectedToolCallAt(idx)"
                      />
                    </UBadge>
                  </div>
                </div>
              </div>
              <div class="space-y-2">
                <div class="flex items-center gap-1.5">
                  <p :class="fieldLabelClass">
                    {{ t("evals.formGuidelinesOptional") }}
                  </p>
                  <UTooltip :text="t('evals.tooltipGuidelines')">
                    <button
                      type="button"
                      class="inline-flex rounded-sm text-muted-foreground hover:text-foreground"
                    >
                      <UIcon
                        name="i-lucide-info"
                        class="size-3.5 shrink-0"
                      />
                    </button>
                  </UTooltip>
                </div>
                <UTextarea
                  v-model="newEvalAdditionalGuidelines"
                  :rows="2"
                  autoresize
                  :placeholder="t('evals.formGuidelinesPlaceholder')"
                  class="w-full"
                />
              </div>
            </template>
          </div>
        </template>
        <template #footer>
          <div
            v-if="newEvalWizardStep === 1"
            class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end"
          >
            <UButton
              color="neutral"
              variant="outline"
              class="w-full sm:w-auto"
              :disabled="submittingEval"
              @click="newEvalOpen = false"
            >
              {{ t("common.cancel") }}
            </UButton>
            <UButton
              color="primary"
              class="w-full sm:w-auto"
              :disabled="submittingEval || !wizardAgentId"
              @click="goWizardNext"
            >
              {{ t("evals.wizardNext") }}
            </UButton>
          </div>
          <div
            v-else
            class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end"
          >
            <UButton
              color="neutral"
              variant="outline"
              class="w-full sm:w-auto"
              :disabled="submittingEval"
              @click="goWizardBack"
            >
              {{ t("evals.wizardBack") }}
            </UButton>
            <UButton
              color="primary"
              class="w-full sm:w-auto"
              :loading="submittingEval"
              :disabled="submittingEval"
              @click="void submitNewEval()"
            >
              {{ t("evals.wizardRunEval") }}
            </UButton>
          </div>
        </template>
      </UModal>
    </div>
  </div>
</template>
