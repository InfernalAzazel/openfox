<script setup lang="ts">
import { ChevronLeft, ChevronRight, RefreshCw } from "lucide-vue-next"
import { computed, onMounted, ref, watch } from "vue"
import { useI18n } from "vue-i18n"
import { VisAxis, VisGroupedBar, VisLine, VisStackedBar, VisXYContainer } from "@unovis/vue"
import { getAgentsAPI, getMetricsAPI, refreshMetricsAPI } from "@/api/os"
import AppPageScaffold from "@/components/AppPageScaffold.vue"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import type { ChartConfig } from "@/components/ui/chart"
import { ChartContainer } from "@/components/ui/chart"
import { getAgentOsBaseUrl } from "@/composables/request"
import { useAppState } from "@/composables/store"
import { cn } from "@/lib/utils"
import type { AgentDetails, AgentOsDayAggregatedMetrics } from "@/types/os"

const { t, locale } = useI18n()
const app = useAppState()
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

/** Database 全量 id（用于 title；无则显示 —） */
const databaseMeta = computed(() => {
  const fullId = agents.value[0]?.db_id?.trim() || ""
  return {
    fullId: fullId || "—",
    table: METRICS_TABLE,
  }
})

/** 参考 UI：过长时前 28 字符 + `...`，完整 id 悬停见 title */
const databaseIdEllipsis = computed(() => {
  const id = databaseMeta.value.fullId
  if (id === "—") {
    return id
  }
  const max = 28
  if (id.length <= max) {
    return id
  }
  return `${id.slice(0, max)}...`
})

function formatCompact(n: number): string {
  const v = Math.abs(n)
  if (v >= 1_000_000) {
    return `${(n / 1_000_000).toFixed(1)}M`
  }
  if (v >= 1_000) {
    return `${(n / 1_000).toFixed(1)}K`
  }
  return String(Math.round(n))
}

type UsageTokenRow = { day: number; t1: number; t2: number }
type UsageUsersRow = { day: number; u: number }
type UsageRunsRow = { day: number; r: number }
type UsageSessionsRow = { day: number; s: number }

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
    if (!row.date) {
      continue
    }
    const d = new Date(row.date)
    if (d.getUTCFullYear() !== y || d.getUTCMonth() !== monthIndex) {
      continue
    }
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
        t1: prev.t1 + t1,
        t2: prev.t2 + t2,
        u: prev.u + u,
        r: prev.r + r,
        s: prev.s + s,
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
  for (const row of series.value.tokens) {
    max = Math.max(max, row.t1 + row.t2)
  }
  const top = max <= 0 ? 100 : Math.ceil(max * 1.08)
  return [0, top]
})

const usersYDomain = computed((): [number, number] => {
  let max = 0
  for (const row of series.value.users) {
    max = Math.max(max, row.u)
  }
  const top = max <= 0 ? 4 : Math.ceil(Math.max(4, max * 1.15))
  return [0, top]
})

const runsYDomain = computed((): [number, number] => {
  let max = 0
  for (const row of series.value.runs) {
    max = Math.max(max, row.r)
  }
  const top = max <= 0 ? 8 : Math.ceil(Math.max(4, max * 1.15))
  return [0, top]
})

const sessionsYDomain = computed((): [number, number] => {
  let max = 0
  for (const row of series.value.sessions) {
    max = Math.max(max, row.s)
  }
  const top = max <= 0 ? 8 : Math.ceil(Math.max(4, max * 1.15))
  return [0, top]
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

const tokensChartConfig = computed(() => {
  void locale.value
  return {
    t1: { label: t("usage.chartInput"), color: "#404040" },
    t2: { label: t("usage.chartOutput"), color: "#a3a3a3" },
  } satisfies ChartConfig
})

const usersChartConfig = computed(() => {
  void locale.value
  return {
    u: { label: t("usage.chartUsers"), color: "#171717" },
  } satisfies ChartConfig
})

const runsChartConfig = computed(() => {
  void locale.value
  return {
    r: { label: t("usage.chartRuns"), color: "#ea580c" },
  } satisfies ChartConfig
})

const sessionsChartConfig = computed(() => {
  void locale.value
  return {
    s: { label: t("usage.chartSessions"), color: "#171717" },
  } satisfies ChartConfig
})

const chartBox = "aspect-auto h-[200px] w-full min-h-[180px]"

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
  if (!base || !token || refreshingMetrics.value) {
    return
  }
  refreshingMetrics.value = true
  try {
    await refreshMetricsAPI(base, token, {
      db_id: dbId,
      table: METRICS_TABLE,
    })
    await loadMetrics()
  } finally {
    refreshingMetrics.value = false
  }
}

watch(
  () =>
    [
      viewMonth.value.getTime(),
      app.value.access_token,
      agents.value[0]?.db_id ?? "",
    ] as const,
  () => {
    void loadMetrics()
  },
)

onMounted(async () => {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim()
  if (!base || !token) {
    return
  }
  agents.value = await getAgentsAPI(base, token)
})
</script>

<template>
  <AppPageScaffold
    content-class="px-3 py-5 sm:px-4 md:px-5"
  >
    <div class="w-full space-y-5 text-foreground sm:space-y-6">
      <div
        class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"
      >
        <div
          class="inline-grid min-w-0 shrink grid-cols-[auto_auto] grid-rows-[auto_auto] gap-x-3 gap-y-0.5 sm:gap-x-4"
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
            :title="databaseMeta.fullId !== '—' ? databaseMeta.fullId : undefined"
          >
            {{ databaseIdEllipsis }}
          </span>
          <span
            class="col-start-2 row-start-2 font-mono text-sm leading-snug font-medium whitespace-nowrap text-foreground"
          >
            {{ databaseMeta.table }}
          </span>
        </div>

        <div class="flex flex-wrap items-center gap-2 md:justify-end">
          <Button
            variant="outline"
            size="sm"
            class="h-9 gap-1.5 border-border bg-card text-xs font-semibold uppercase tracking-wide"
            type="button"
            :title="t('usage.refreshMetricsTitle')"
            :disabled="refreshingMetrics || loadingMetrics"
            @click="void refreshMetricsAndReload()"
          >
            <RefreshCw
              class="size-3.5 opacity-70"
              :class="refreshingMetrics ? 'animate-spin' : ''"
              aria-hidden="true"
            />
            {{ t("usage.refreshMetrics") }}
          </Button>

          <div
            class="flex items-center rounded-md border border-border bg-muted/50 dark:bg-muted/30"
          >
            <Button
              variant="ghost"
              size="icon"
              class="h-9 w-9 shrink-0 rounded-none rounded-l-md"
              type="button"
              :aria-label="t('usage.prevMonth')"
              @click="shiftMonth(-1)"
            >
              <ChevronLeft class="size-4" />
            </Button>
            <span
              class="min-w-26 select-none px-1 py-2 text-center text-xs font-semibold tabular-nums tracking-wide text-foreground"
            >
              {{ monthLabel }}
            </span>
            <Button
              variant="ghost"
              size="icon"
              class="h-9 w-9 shrink-0 rounded-none rounded-r-md"
              type="button"
              :aria-label="t('usage.nextMonth')"
              @click="shiftMonth(1)"
            >
              <ChevronRight class="size-4" />
            </Button>
          </div>
        </div>
      </div>

      <div
        class="rounded-xl border border-border bg-card px-4 py-4 shadow-sm sm:px-5"
      >
        <div class="grid gap-4 sm:grid-cols-2">
          <!-- Total tokens -->
          <Card
            :class="
              cn(
                'gap-0 overflow-hidden rounded-lg border-border py-0 shadow-none',
              )
            "
          >
            <div
              class="flex items-start justify-between gap-3 border-b border-border px-4 py-3"
            >
              <span class="text-sm text-muted-foreground">{{ t("usage.cardTotalTokens") }}</span>
              <div class="flex items-center gap-1">
                <span class="text-lg font-semibold tabular-nums tracking-tight">
                  {{ formatCompact(totalTokens) }}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  class="h-8 w-8 text-muted-foreground hover:text-foreground"
                  type="button"
                  :title="t('usage.refreshCardTitle')"
                  :aria-label="t('usage.refreshCardTitle')"
                  :disabled="refreshingMetrics || loadingMetrics"
                  @click="void refreshMetricsAndReload()"
                >
                  <RefreshCw
                    class="size-3.5"
                    :class="refreshingMetrics ? 'animate-spin' : ''"
                  />
                </Button>
              </div>
            </div>
            <CardContent class="px-2 pb-3 pt-2">
              <ChartContainer
                :config="tokensChartConfig"
                :class="chartBox"
                :cursor="false"
              >
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
                    :color="(_d: UsageTokenRow, i: number) => (i === 0 ? '#404040' : '#a3a3a3')"
                    :rounded-corners="2"
                  />
                  <VisAxis
                    type="x"
                    :x="(d: UsageTokenRow) => d.day"
                    :tick-line="false"
                    :domain-line="false"
                    :grid-line="false"
                    :tick-values="xTickValues"
                    :tick-format="(n: number) => String(n)"
                    :num-ticks="xTickValues.length"
                    :tick-text-font-size="'11px'"
                    :tick-text-color="'#737373'"
                    :class="axisMuted"
                  />
                  <VisAxis
                    type="y"
                    :num-ticks="4"
                    :tick-line="false"
                    :domain-line="false"
                    :grid-line="true"
                    :tick-format="
                      (n: number) =>
                        n >= 1000 ? `${Math.round(n / 1000)}K` : String(n)
                    "
                    :tick-text-font-size="'11px'"
                    :tick-text-color="'#737373'"
                    :class="axisMuted"
                  />
                </VisXYContainer>
              </ChartContainer>
            </CardContent>
          </Card>

          <!-- Users -->
          <Card
            :class="
              cn(
                'gap-0 overflow-hidden rounded-lg border-border py-0 shadow-none',
              )
            "
          >
            <div
              class="flex items-start justify-between gap-3 border-b border-border px-4 py-3"
            >
              <span class="text-sm text-muted-foreground">{{ t("usage.cardUsers") }}</span>
              <div class="flex items-center gap-1">
                <span class="text-lg font-semibold tabular-nums tracking-tight">
                  {{ totalUsers }}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  class="h-8 w-8 text-muted-foreground hover:text-foreground"
                  type="button"
                  :title="t('usage.refreshCardTitle')"
                  :aria-label="t('usage.refreshCardTitle')"
                  :disabled="refreshingMetrics || loadingMetrics"
                  @click="void refreshMetricsAndReload()"
                >
                  <RefreshCw
                    class="size-3.5"
                    :class="refreshingMetrics ? 'animate-spin' : ''"
                  />
                </Button>
              </div>
            </div>
            <CardContent class="px-2 pb-3 pt-2">
              <ChartContainer
                :config="usersChartConfig"
                :class="chartBox"
                :cursor="false"
              >
                <VisXYContainer
                  :data="series.users"
                  :margin="{ left: 8, right: 8, top: 8, bottom: 28 }"
                  :x-domain="xDomain"
                  :y-domain="usersYDomain"
                >
                  <VisGroupedBar
                    :x="(d: UsageUsersRow) => d.day"
                    :y="[(d: UsageUsersRow) => d.u]"
                    :data-step="1"
                    :group-padding="0.35"
                    :color="() => '#171717'"
                    :rounded-corners="1"
                  />
                  <VisAxis
                    type="x"
                    :x="(d: UsageUsersRow) => d.day"
                    :tick-line="false"
                    :domain-line="false"
                    :grid-line="false"
                    :tick-values="xTickValues"
                    :tick-format="(n: number) => String(n)"
                    :num-ticks="xTickValues.length"
                    :tick-text-font-size="'11px'"
                    :tick-text-color="'#737373'"
                    :class="axisMuted"
                  />
                  <VisAxis
                    type="y"
                    :num-ticks="3"
                    :tick-line="false"
                    :domain-line="false"
                    :grid-line="true"
                    :tick-format="(n: number) => String(Math.round(n))"
                    :tick-text-font-size="'11px'"
                    :tick-text-color="'#737373'"
                    :class="axisMuted"
                  />
                </VisXYContainer>
              </ChartContainer>
            </CardContent>
          </Card>

          <!-- Agent Runs -->
          <Card
            :class="
              cn(
                'gap-0 overflow-hidden rounded-lg border-border py-0 shadow-none',
              )
            "
          >
            <div
              class="flex items-start justify-between gap-3 border-b border-border px-4 py-3"
            >
              <span class="text-sm text-muted-foreground">{{ t("usage.cardAgentRuns") }}</span>
              <div class="flex items-center gap-1">
                <span class="text-lg font-semibold tabular-nums tracking-tight">
                  {{ totalRuns }}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  class="h-8 w-8 text-muted-foreground hover:text-foreground"
                  type="button"
                  :title="t('usage.refreshCardTitle')"
                  :aria-label="t('usage.refreshCardTitle')"
                  :disabled="refreshingMetrics || loadingMetrics"
                  @click="void refreshMetricsAndReload()"
                >
                  <RefreshCw
                    class="size-3.5"
                    :class="refreshingMetrics ? 'animate-spin' : ''"
                  />
                </Button>
              </div>
            </div>
            <CardContent class="px-2 pb-3 pt-2">
              <ChartContainer
                :config="runsChartConfig"
                :class="chartBox"
                :cursor="true"
              >
                <VisXYContainer
                  :data="series.runs"
                  :margin="{ left: 8, right: 8, top: 8, bottom: 28 }"
                  :x-domain="xDomain"
                  :y-domain="runsYDomain"
                >
                  <VisLine
                    :x="(d: UsageRunsRow) => d.day"
                    :y="(d: UsageRunsRow) => d.r"
                    :color="'#ea580c'"
                    :line-width="2"
                  />
                  <VisAxis
                    type="x"
                    :x="(d: UsageRunsRow) => d.day"
                    :tick-line="false"
                    :domain-line="false"
                    :grid-line="false"
                    :tick-values="xTickValues"
                    :tick-format="(n: number) => String(n)"
                    :num-ticks="xTickValues.length"
                    :tick-text-font-size="'11px'"
                    :tick-text-color="'#737373'"
                    :class="axisMuted"
                  />
                  <VisAxis
                    type="y"
                    :num-ticks="4"
                    :tick-line="false"
                    :domain-line="false"
                    :grid-line="true"
                    :tick-format="(n: number) => String(Math.round(n))"
                    :tick-text-font-size="'11px'"
                    :tick-text-color="'#737373'"
                    :class="axisMuted"
                  />
                </VisXYContainer>
              </ChartContainer>
            </CardContent>
          </Card>

          <!-- Agent Sessions -->
          <Card
            :class="
              cn(
                'gap-0 overflow-hidden rounded-lg border-border py-0 shadow-none',
              )
            "
          >
            <div
              class="flex items-start justify-between gap-3 border-b border-border px-4 py-3"
            >
              <span class="text-sm text-muted-foreground">{{ t("usage.cardAgentSessions") }}</span>
              <div class="flex items-center gap-1">
                <span class="text-lg font-semibold tabular-nums tracking-tight">
                  {{ totalSessions }}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  class="h-8 w-8 text-muted-foreground hover:text-foreground"
                  type="button"
                  :title="t('usage.refreshCardTitle')"
                  :aria-label="t('usage.refreshCardTitle')"
                  :disabled="refreshingMetrics || loadingMetrics"
                  @click="void refreshMetricsAndReload()"
                >
                  <RefreshCw
                    class="size-3.5"
                    :class="refreshingMetrics ? 'animate-spin' : ''"
                  />
                </Button>
              </div>
            </div>
            <CardContent class="px-2 pb-3 pt-2">
              <ChartContainer
                :config="sessionsChartConfig"
                :class="chartBox"
                :cursor="false"
              >
                <VisXYContainer
                  :data="series.sessions"
                  :margin="{ left: 8, right: 8, top: 8, bottom: 28 }"
                  :x-domain="xDomain"
                  :y-domain="sessionsYDomain"
                >
                  <VisLine
                    :x="(d: UsageSessionsRow) => d.day"
                    :y="(d: UsageSessionsRow) => d.s"
                    :color="'#171717'"
                    :line-width="2"
                  />
                  <VisAxis
                    type="x"
                    :x="(d: UsageSessionsRow) => d.day"
                    :tick-line="false"
                    :domain-line="false"
                    :grid-line="false"
                    :tick-values="xTickValues"
                    :tick-format="(n: number) => String(n)"
                    :num-ticks="xTickValues.length"
                    :tick-text-font-size="'11px'"
                    :tick-text-color="'#737373'"
                    :class="axisMuted"
                  />
                  <VisAxis
                    type="y"
                    :num-ticks="3"
                    :tick-line="false"
                    :domain-line="false"
                    :grid-line="true"
                    :tick-format="(n: number) => String(Math.round(n))"
                    :tick-text-font-size="'11px'"
                    :tick-text-color="'#737373'"
                    :class="axisMuted"
                  />
                </VisXYContainer>
              </ChartContainer>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  </AppPageScaffold>
</template>
