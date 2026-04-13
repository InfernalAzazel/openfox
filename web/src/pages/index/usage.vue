<script setup lang="ts">
import { VisAxis, VisGroupedBar, VisLine, VisStackedBar, VisXYContainer } from "@unovis/vue"
import { useDark } from "@vueuse/core"
import { computed, onMounted, ref, watch } from "vue"
import { useI18n } from "vue-i18n"
import { getAgentsAPI, getMetricsAPI, refreshMetricsAPI } from "@/api/os"
import { getAgentOsBaseUrl } from "@/composables/request"
import { useAppState } from "@/composables/store"
import type { AgentDetails, AgentOsDayAggregatedMetrics } from "@/types/os"

const { t, locale } = useI18n()
const app = useAppState()
const isDark = useDark()
const agents = ref<AgentDetails[]>([])

const METRICS_TABLE = "agno_metrics"

const metricsRows = ref<AgentOsDayAggregatedMetrics[]>([])
const loadingMetrics = ref(false)
const refreshingMetrics = ref(false)

/** 当前查看月（默认本月） */
const viewMonth = ref(new Date())

const daysInMonth = computed(() => {
  const y = viewMonth.value.getFullYear()
  const m = viewMonth.value.getMonth()
  return new Date(y, m + 1, 0).getDate()
})

const monthLabel = computed(() => {
  void locale.value
  const d = viewMonth.value
  if (locale.value === "zh-CN") {
    return new Intl.DateTimeFormat("zh-CN", {
      year: "numeric",
      month: "long",
    }).format(d)
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    year: "numeric",
  })
    .format(d)
    .toUpperCase()
})

const xTickValues = computed(() => {
  const last = daysInMonth.value
  const candidates = [1, 8, 15, 22, 29].filter((d) => d <= last)
  if (last >= 22 && !candidates.includes(last)) {
    candidates.push(last)
  }
  return [...new Set(candidates)].sort((a, b) => a - b)
})

const xDomain = computed((): [number, number] => [1, daysInMonth.value])

function shiftMonth(delta: number) {
  const d = new Date(viewMonth.value)
  d.setMonth(d.getMonth() + delta)
  viewMonth.value = d
}

const databaseMeta = computed(() => {
  const fullId = agents.value[0]?.db_id?.trim() || ""
  return {
    fullId: fullId || "—",
    table: METRICS_TABLE,
  }
})

const databaseIdEllipsis = computed(() => {
  const id = databaseMeta.value.fullId
  if (id === "—") return id
  const max = 28
  return id.length <= max ? id : `${id.slice(0, max)}...`
})

function formatCompact(n: number): string {
  const v = Math.abs(n)
  if (v >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(Math.round(n))
}

type UsageTokenRow = { day: number; t1: number; t2: number }
type UsageUsersRow = { day: number; u: number }
type UsageRunsRow = { day: number; r: number }
type UsageSessionsRow = { day: number; s: number }

/** Unovis 用固定 hex，需按主题切换，否则暗色下深灰条/线贴背景 */
const chartAxisTickColor = computed(() =>
  isDark.value ? "#a1a1aa" : "#737373",
)

const tokenStackBarColor = computed(
  () => (_d: UsageTokenRow, i: number) =>
    isDark.value
      ? (i === 0 ? "#38bdf8" : "#94a3b8")
      : (i === 0 ? "#404040" : "#a3a3a3"),
)

const usersBarColor = computed(() => () =>
  isDark.value ? "#818cf8" : "#171717",
)

const runsLineColor = computed(() =>
  isDark.value ? "#fb923c" : "#ea580c",
)

const sessionsLineColor = computed(() =>
  isDark.value ? "#c084fc" : "#171717",
)

function ymdUTC(y: number, monthIndex: number, day: number): string {
  return `${y}-${String(monthIndex + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`
}

function buildSeriesFromMetrics(
  rows: AgentOsDayAggregatedMetrics[],
  dayCount: number,
  y: number,
  monthIndex: number,
) {
  type Agg = { t1: number; t2: number; u: number; r: number; s: number }
  const byDay = new Map<number, Agg>()
  for (const row of rows) {
    if (!row.date) continue
    const d = new Date(row.date)
    if (d.getUTCFullYear() !== y || d.getUTCMonth() !== monthIndex) continue
    const dom = d.getUTCDate()
    const tm = row.token_metrics
    const t1 = Number(tm?.input_tokens ?? 0)
    const t2 = Number(tm?.output_tokens ?? 0)
    const u = Number(row.users_count ?? 0)
    const r = Number(row.agent_runs_count ?? 0)
    const s = Number(row.agent_sessions_count ?? 0)
    const prev = byDay.get(dom)
    if (prev) {
      byDay.set(dom, {
        t1: prev.t1 + t1, t2: prev.t2 + t2,
        u: prev.u + u, r: prev.r + r, s: prev.s + s,
      })
    } else {
      byDay.set(dom, { t1, t2, u, r, s })
    }
  }
  const tokens: UsageTokenRow[] = []
  const users: UsageUsersRow[] = []
  const runs: UsageRunsRow[] = []
  const sessions: UsageSessionsRow[] = []
  for (let day = 1; day <= dayCount; day++) {
    const v = byDay.get(day)
    tokens.push({ day, t1: v?.t1 ?? 0, t2: v?.t2 ?? 0 })
    users.push({ day, u: v?.u ?? 0 })
    runs.push({ day, r: v?.r ?? 0 })
    sessions.push({ day, s: v?.s ?? 0 })
  }
  return { tokens, users, runs, sessions }
}

const series = computed(() => {
  const y = viewMonth.value.getFullYear()
  const m0 = viewMonth.value.getMonth()
  return buildSeriesFromMetrics(metricsRows.value, daysInMonth.value, y, m0)
})

const tokenYDomain = computed((): [number, number] => {
  let max = 0
  for (const row of series.value.tokens) max = Math.max(max, row.t1 + row.t2)
  return [0, max <= 0 ? 100 : Math.ceil(max * 1.08)]
})

const usersYDomain = computed((): [number, number] => {
  let max = 0
  for (const row of series.value.users) max = Math.max(max, row.u)
  return [0, max <= 0 ? 4 : Math.ceil(Math.max(4, max * 1.15))]
})

const runsYDomain = computed((): [number, number] => {
  let max = 0
  for (const row of series.value.runs) max = Math.max(max, row.r)
  return [0, max <= 0 ? 8 : Math.ceil(Math.max(4, max * 1.15))]
})

const sessionsYDomain = computed((): [number, number] => {
  let max = 0
  for (const row of series.value.sessions) max = Math.max(max, row.s)
  return [0, max <= 0 ? 8 : Math.ceil(Math.max(4, max * 1.15))]
})

const totalTokens = computed(() =>
  series.value.tokens.reduce((a, row) => a + row.t1 + row.t2, 0),
)
const totalUsers = computed(() =>
  series.value.users.reduce((a, row) => a + row.u, 0),
)
const totalRuns = computed(() =>
  series.value.runs.reduce((a, row) => a + row.r, 0),
)
const totalSessions = computed(() =>
  series.value.sessions.reduce((a, row) => a + row.s, 0),
)

const axisMuted =
  "[&_.tick_line]:stroke-border/40 [&_.grid_line]:stroke-border/25 [&_.domain_line]:stroke-border/30"

async function loadMetrics() {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim()
  const dbId = agents.value[0]?.db_id?.trim()
  if (!base || !token) {
    metricsRows.value = []
    return
  }
  loadingMetrics.value = true
  try {
    const y = viewMonth.value.getFullYear()
    const m0 = viewMonth.value.getMonth()
    const lastDay = new Date(y, m0 + 1, 0).getDate()
    const res = await getMetricsAPI(base, token, {
      starting_date: ymdUTC(y, m0, 1),
      ending_date: ymdUTC(y, m0, lastDay),
      db_id: dbId,
      table: METRICS_TABLE,
    })
    metricsRows.value = res?.metrics ?? []
  } finally {
    loadingMetrics.value = false
  }
}

async function refreshMetricsAndReload() {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim()
  const dbId = agents.value[0]?.db_id?.trim()
  if (!base || !token || refreshingMetrics.value) return
  refreshingMetrics.value = true
  try {
    await refreshMetricsAPI(base, token, { db_id: dbId, table: METRICS_TABLE })
    await loadMetrics()
  } finally {
    refreshingMetrics.value = false
  }
}

watch(
  () => [viewMonth.value.getTime(), app.value.access_token, agents.value[0]?.db_id ?? ""] as const,
  () => { void loadMetrics() },
)

onMounted(async () => {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim()
  if (!base || !token) return
  agents.value = await getAgentsAPI(base, token)
})

const chartCardUi = {
  root: "gap-0 overflow-hidden rounded-lg py-0 shadow-none",
  header: "border-b border-default px-4 py-3",
  body: "px-2 py-2",
}
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col overflow-auto bg-background">
    <div class="w-full space-y-5 p-4 text-foreground md:p-6">
      <!-- 顶部 meta + 控件 -->
      <div
        class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"
      >
        <div
          class="inline-grid min-w-0 shrink grid-cols-[auto_auto] grid-rows-[auto_auto] gap-x-3 gap-y-0.5 sm:gap-x-4"
        >
          <span class="col-start-1 row-start-1 text-xs leading-none text-muted-foreground">
            {{ t("common.metaDatabase") }}
          </span>
          <span class="col-start-2 row-start-1 text-xs leading-none text-muted-foreground">
            {{ t("common.metaTable") }}
          </span>
          <span
            class="col-start-1 row-start-2 min-w-0 max-w-[min(100%,20rem)] font-mono text-sm leading-snug font-medium whitespace-nowrap sm:max-w-[24rem]"
            :title="databaseMeta.fullId !== '—' ? databaseMeta.fullId : undefined"
          >
            {{ databaseIdEllipsis }}
          </span>
          <span class="col-start-2 row-start-2 font-mono text-sm leading-snug font-medium whitespace-nowrap">
            {{ databaseMeta.table }}
          </span>
        </div>

        <div
          class="flex flex-wrap items-center gap-2 md:justify-end [&_button]:focus-visible:z-10"
        >
          <UButton
            variant="outline"
            color="neutral"
            size="sm"
            square
            icon="i-lucide-refresh-cw"
            :aria-label="t('usage.refreshMetricsTitle')"
            :title="t('usage.refreshMetricsTitle')"
            :disabled="refreshingMetrics || loadingMetrics"
            :loading="refreshingMetrics"
            @click="void refreshMetricsAndReload()"
          />

          <!-- 单一边框 + divide-x：避免内层 outline 与外壳叠成双线条；内侧 ghost 与左侧独立 outline 刷新形成「主按钮 + 成组控件」层次 -->
          <div
            class="inline-flex shrink-0 items-center divide-x divide-default overflow-hidden rounded-md border border-default bg-background"
          >
            <UButton
              variant="ghost"
              color="neutral"
              size="sm"
              square
              class="rounded-none"
              icon="i-lucide-chevron-left"
              :aria-label="t('usage.prevMonth')"
              :title="t('usage.prevMonth')"
              @click="shiftMonth(-1)"
            />
            <span
              class="flex min-w-28 max-w-[11rem] shrink-0 select-none items-center justify-center bg-background px-2.5 text-center text-xs font-medium tabular-nums text-foreground sm:min-w-32 sm:max-w-[13rem]"
            >
              {{ monthLabel }}
            </span>
            <UButton
              variant="ghost"
              color="neutral"
              size="sm"
              square
              class="rounded-none"
              icon="i-lucide-chevron-right"
              :aria-label="t('usage.nextMonth')"
              :title="t('usage.nextMonth')"
              @click="shiftMonth(1)"
            />
          </div>
        </div>
      </div>

      <!-- 图表 2×2 -->
      <div class="rounded-xl border border-default bg-default p-4 shadow-sm sm:p-5">
        <div class="grid gap-4 sm:grid-cols-2">
          <!-- Total Tokens -->
          <UCard :ui="chartCardUi">
            <template #header>
              <div class="flex items-start justify-between gap-3">
                <span class="text-sm text-muted-foreground">{{ t("usage.cardTotalTokens") }}</span>
                <div class="flex items-center gap-1">
                  <span class="text-lg font-semibold tabular-nums tracking-tight">
                    {{ formatCompact(totalTokens) }}
                  </span>
                  <UButton
                    variant="ghost"
                    color="neutral"
                    square
                    class="size-8"
                    icon="i-lucide-refresh-cw"
                    :title="t('usage.refreshCardTitle')"
                    :disabled="refreshingMetrics || loadingMetrics"
                    :loading="refreshingMetrics"
                    @click="void refreshMetricsAndReload()"
                  />
                </div>
              </div>
            </template>

            <div class="aspect-auto h-[200px] w-full min-h-[180px]">
              <VisXYContainer
                :data="series.tokens"
                :margin="{ left: 8, right: 8, top: 8, bottom: 28 }"
                :x-domain="xDomain"
                :y-domain="tokenYDomain"
              >
                <VisStackedBar
                  :x="(d: UsageTokenRow) => d.day"
                  :y="[(d: UsageTokenRow) => d.t1, (d: UsageTokenRow) => d.t2]"
                  :data-step="1"
                  :bar-padding="0.35"
                  :color="tokenStackBarColor"
                  :rounded-corners="2"
                />
                <VisAxis type="x" :x="(d: UsageTokenRow) => d.day" :tick-line="false" :domain-line="false" :grid-line="false" :tick-values="xTickValues" :tick-format="(n: number) => String(n)" :num-ticks="xTickValues.length" :tick-text-font-size="'11px'" :tick-text-color="chartAxisTickColor" :class="axisMuted" />
                <VisAxis type="y" :num-ticks="4" :tick-line="false" :domain-line="false" :grid-line="true" :tick-format="(n: number) => n >= 1000 ? `${Math.round(n / 1000)}K` : String(n)" :tick-text-font-size="'11px'" :tick-text-color="chartAxisTickColor" :class="axisMuted" />
              </VisXYContainer>
            </div>
          </UCard>

          <!-- Users -->
          <UCard :ui="chartCardUi">
            <template #header>
              <div class="flex items-start justify-between gap-3">
                <span class="text-sm text-muted-foreground">{{ t("usage.cardUsers") }}</span>
                <div class="flex items-center gap-1">
                  <span class="text-lg font-semibold tabular-nums tracking-tight">{{ totalUsers }}</span>
                  <UButton
                    variant="ghost"
                    color="neutral"
                    square
                    class="size-8"
                    icon="i-lucide-refresh-cw"
                    :title="t('usage.refreshCardTitle')"
                    :disabled="refreshingMetrics || loadingMetrics"
                    :loading="refreshingMetrics"
                    @click="void refreshMetricsAndReload()"
                  />
                </div>
              </div>
            </template>

            <div class="aspect-auto h-[200px] w-full min-h-[180px]">
              <VisXYContainer
                :data="series.users"
                :margin="{ left: 8, right: 8, top: 8, bottom: 28 }"
                :x-domain="xDomain"
                :y-domain="usersYDomain"
              >
                <VisGroupedBar :x="(d: UsageUsersRow) => d.day" :y="[(d: UsageUsersRow) => d.u]" :data-step="1" :group-padding="0.35" :color="usersBarColor" :rounded-corners="1" />
                <VisAxis type="x" :x="(d: UsageUsersRow) => d.day" :tick-line="false" :domain-line="false" :grid-line="false" :tick-values="xTickValues" :tick-format="(n: number) => String(n)" :num-ticks="xTickValues.length" :tick-text-font-size="'11px'" :tick-text-color="chartAxisTickColor" :class="axisMuted" />
                <VisAxis type="y" :num-ticks="3" :tick-line="false" :domain-line="false" :grid-line="true" :tick-format="(n: number) => String(Math.round(n))" :tick-text-font-size="'11px'" :tick-text-color="chartAxisTickColor" :class="axisMuted" />
              </VisXYContainer>
            </div>
          </UCard>

          <!-- Agent Runs -->
          <UCard :ui="chartCardUi">
            <template #header>
              <div class="flex items-start justify-between gap-3">
                <span class="text-sm text-muted-foreground">{{ t("usage.cardAgentRuns") }}</span>
                <div class="flex items-center gap-1">
                  <span class="text-lg font-semibold tabular-nums tracking-tight">{{ totalRuns }}</span>
                  <UButton
                    variant="ghost"
                    color="neutral"
                    square
                    class="size-8"
                    icon="i-lucide-refresh-cw"
                    :title="t('usage.refreshCardTitle')"
                    :disabled="refreshingMetrics || loadingMetrics"
                    :loading="refreshingMetrics"
                    @click="void refreshMetricsAndReload()"
                  />
                </div>
              </div>
            </template>

            <div class="aspect-auto h-[200px] w-full min-h-[180px]">
              <VisXYContainer
                :data="series.runs"
                :margin="{ left: 8, right: 8, top: 8, bottom: 28 }"
                :x-domain="xDomain"
                :y-domain="runsYDomain"
              >
                <VisLine :x="(d: UsageRunsRow) => d.day" :y="(d: UsageRunsRow) => d.r" :color="runsLineColor" :line-width="2" />
                <VisAxis type="x" :x="(d: UsageRunsRow) => d.day" :tick-line="false" :domain-line="false" :grid-line="false" :tick-values="xTickValues" :tick-format="(n: number) => String(n)" :num-ticks="xTickValues.length" :tick-text-font-size="'11px'" :tick-text-color="chartAxisTickColor" :class="axisMuted" />
                <VisAxis type="y" :num-ticks="4" :tick-line="false" :domain-line="false" :grid-line="true" :tick-format="(n: number) => String(Math.round(n))" :tick-text-font-size="'11px'" :tick-text-color="chartAxisTickColor" :class="axisMuted" />
              </VisXYContainer>
            </div>
          </UCard>

          <!-- Agent Sessions -->
          <UCard :ui="chartCardUi">
            <template #header>
              <div class="flex items-start justify-between gap-3">
                <span class="text-sm text-muted-foreground">{{ t("usage.cardAgentSessions") }}</span>
                <div class="flex items-center gap-1">
                  <span class="text-lg font-semibold tabular-nums tracking-tight">{{ totalSessions }}</span>
                  <UButton
                    variant="ghost"
                    color="neutral"
                    square
                    class="size-8"
                    icon="i-lucide-refresh-cw"
                    :title="t('usage.refreshCardTitle')"
                    :disabled="refreshingMetrics || loadingMetrics"
                    :loading="refreshingMetrics"
                    @click="void refreshMetricsAndReload()"
                  />
                </div>
              </div>
            </template>

            <div class="aspect-auto h-[200px] w-full min-h-[180px]">
              <VisXYContainer
                :data="series.sessions"
                :margin="{ left: 8, right: 8, top: 8, bottom: 28 }"
                :x-domain="xDomain"
                :y-domain="sessionsYDomain"
              >
                <VisLine :x="(d: UsageSessionsRow) => d.day" :y="(d: UsageSessionsRow) => d.s" :color="sessionsLineColor" :line-width="2" />
                <VisAxis type="x" :x="(d: UsageSessionsRow) => d.day" :tick-line="false" :domain-line="false" :grid-line="false" :tick-values="xTickValues" :tick-format="(n: number) => String(n)" :num-ticks="xTickValues.length" :tick-text-font-size="'11px'" :tick-text-color="chartAxisTickColor" :class="axisMuted" />
                <VisAxis type="y" :num-ticks="3" :tick-line="false" :domain-line="false" :grid-line="true" :tick-format="(n: number) => String(Math.round(n))" :tick-text-font-size="'11px'" :tick-text-color="chartAxisTickColor" :class="axisMuted" />
              </VisXYContainer>
            </div>
          </UCard>
        </div>
      </div>
    </div>
  </div>
</template>
