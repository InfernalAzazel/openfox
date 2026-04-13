<script setup lang="ts">
import { ref } from "vue"
import { useI18n } from "vue-i18n"
import type { ToolCall } from "@/types/os"

const { t } = useI18n()

const props = defineProps<{
  /** 与 agent-ui {@link ChatMessage.tool_calls} 一致 */
  toolCalls: ToolCall[]
}>()

const copiedId = ref<string | null>(null)

function formatTagLabel(toolName: string): string {
  return toolName.replace(/\s+/g, "_").toUpperCase()
}

function tagKey(tc: ToolCall, index: number): string {
  if (tc.tool_call_id?.trim()) return tc.tool_call_id
  return `tag-${index}-${tc.tool_name}`
}

async function copyText(text: string, id: string) {
  try {
    await navigator.clipboard.writeText(text)
    copiedId.value = id
    setTimeout(() => {
      copiedId.value = null
    }, 1600)
  } catch {
    /* ignore */
  }
}

function copyPartKey(ti: number, part: string): string {
  return `detail-${ti}-${part}`
}

function formatToolArgsRecord(args: Record<string, string>): string {
  const e = Object.entries(args).filter(([k]) => k !== "")
  if (!e.length) return "—"
  return e.map(([k, v]) => `${k} : ${v}`).join("\n")
}

function prettyJsonBlock(raw: string): string {
  const t = raw.trim()
  if (!t) return "—"
  try {
    return JSON.stringify(JSON.parse(t) as unknown, null, 2)
  } catch {
    return raw
  }
}

function metricsFromOutput(out: string | undefined): string | null {
  if (!out?.trim()) return null
  try {
    const o = JSON.parse(out) as Record<string, unknown>
    const m = o.metrics as Record<string, unknown> | undefined
    const dur =
      typeof o.duration === "number"
        ? o.duration
        : typeof o.duration_ms === "number"
          ? o.duration_ms
          : typeof m?.duration === "number"
            ? m.duration
            : typeof m?.time === "number"
              ? m.time
              : typeof o.time === "number"
                ? o.time
                : null
    if (dur !== null) {
      return `Duration: ${dur} ms`
    }
    if (m && typeof m === "object") {
      const lines = Object.entries(m)
        .filter(([, v]) => typeof v === "number" || typeof v === "string")
        .map(([k, v]) => `${k}: ${String(v)}`)
      if (lines.length) return lines.join("\n")
    }
  } catch {
    return null
  }
  return null
}

function formatToolResultForCard(raw: string): string {
  const t = raw.trim()
  if (!t) return "—"
  try {
    const o = JSON.parse(t) as Record<string, unknown>
    if ("STDERR" in o || "STDOUT" in o) {
      const parts: string[] = []
      if (o.STDERR != null && String(o.STDERR))
        parts.push(`STDERR:\n${String(o.STDERR)}`)
      if (o.STDOUT != null && String(o.STDOUT))
        parts.push(`STDOUT:\n${String(o.STDOUT)}`)
      if (parts.length) return parts.join("\n\n")
    }
  } catch {
    /* raw text */
  }
  return prettyJsonBlock(raw)
}

function sectionBoxClass(): string {
  return "flex min-h-9 items-stretch gap-0 overflow-hidden rounded-lg border border-border/80 bg-muted/40"
}

function toolResultPayload(tc: ToolCall): string | undefined {
  return tc.content ?? undefined
}

function resultText(tc: ToolCall): string {
  const raw = toolResultPayload(tc)
  if (!raw?.trim()) return "—"
  return formatToolResultForCard(raw)
}

function hasToolOut(tc: ToolCall): boolean {
  return Boolean(tc.content?.trim())
}
</script>

<template>
  <div
    class="w-full rounded-xl border border-border bg-muted/50 px-3 py-3 dark:border-white/10 dark:bg-secondary/50 md:px-4"
    role="region"
    :aria-label="t('tools.regionAria')"
  >
    <h2
      class="mb-2.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground"
    >
      TOOLS
    </h2>
    <div class="flex flex-wrap gap-2">
      <UPopover
        v-for="(tc, ti) in props.toolCalls"
        :key="`${ti}-${tagKey(tc, ti)}`"
        mode="hover"
        :open-delay="280"
      >
        <button
          type="button"
          class="inline-flex max-w-full cursor-default items-center gap-1.5 rounded-full border border-border bg-muted py-1 pl-2.5 pr-2 font-mono text-[11px] font-semibold uppercase tracking-wide text-foreground shadow-sm outline-none transition-colors hover:bg-muted/80 focus-visible:ring-2 focus-visible:ring-ring dark:border-white/12 dark:bg-secondary/90 dark:hover:bg-secondary"
          :aria-label="t('tools.toolHoverAria', { name: formatTagLabel(tc.tool_name) })"
        >
          <span class="min-w-0 truncate">{{ formatTagLabel(tc.tool_name) }}</span>
          <UIcon name="i-lucide-info" class="size-3.5 shrink-0 opacity-70" aria-hidden="true" />
        </button>

        <template #content>
          <div class="w-[min(calc(100vw-2rem),22rem)] max-h-[min(70vh,26rem)] overflow-y-auto p-3 space-y-3 text-xs">
            <p class="font-mono text-[13px] font-bold tracking-wide text-foreground">
              {{ formatTagLabel(tc.tool_name) }}
            </p>

            <div>
              <div class="mb-1 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                <UIcon name="i-lucide-hammer" class="size-3 shrink-0 opacity-80" aria-hidden="true" />
                {{ t("tools.toolName") }}
              </div>
              <div :class="sectionBoxClass()">
                <pre class="max-h-20 min-w-0 flex-1 overflow-auto whitespace-pre-wrap break-all px-2.5 py-1.5 font-mono text-[11px] text-foreground">{{ tc.tool_name }}</pre>
                <UButton
                  variant="ghost"
                  color="neutral"
                  square
                  class="size-8 shrink-0 rounded-none border-l border-border/80"
                  :title="t('common.copy')"
                  @click="copyText(tc.tool_name, copyPartKey(ti, 'name'))"
                >
                  <UIcon
                    v-if="copiedId === copyPartKey(ti, 'name')"
                    name="i-lucide-check"
                    class="size-3.5 text-green-600 dark:text-green-400"
                  />
                  <UIcon v-else name="i-lucide-copy" class="size-3.5 opacity-70" />
                </UButton>
              </div>
            </div>

            <div>
              <div class="mb-1 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                <UIcon name="i-lucide-pencil" class="size-3 shrink-0 opacity-80" aria-hidden="true" />
                {{ t("tools.toolArgs") }}
              </div>
              <div :class="sectionBoxClass()">
                <pre class="max-h-36 min-w-0 flex-1 overflow-auto whitespace-pre-wrap break-all px-2.5 py-1.5 font-mono text-[10px] leading-relaxed text-foreground">{{ formatToolArgsRecord(tc.tool_args) }}</pre>
                <UButton
                  variant="ghost"
                  color="neutral"
                  square
                  class="size-8 shrink-0 self-start rounded-none border-l border-border/80"
                  :title="t('common.copy')"
                  @pointerdown.stop
                  @click="copyText(formatToolArgsRecord(tc.tool_args), copyPartKey(ti, 'args'))"
                >
                  <UIcon
                    v-if="copiedId === copyPartKey(ti, 'args')"
                    name="i-lucide-check"
                    class="size-3.5 text-green-600 dark:text-green-400"
                  />
                  <UIcon v-else name="i-lucide-copy" class="size-3.5 opacity-70" />
                </UButton>
              </div>
            </div>

            <div v-if="metricsFromOutput(toolResultPayload(tc))">
              <div class="mb-1 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                <UIcon name="i-lucide-chart-column" class="size-3 shrink-0 opacity-80" aria-hidden="true" />
                {{ t("tools.toolMetrics") }}
              </div>
              <div :class="sectionBoxClass()">
                <pre class="max-h-20 min-w-0 flex-1 overflow-auto whitespace-pre-wrap px-2.5 py-1.5 font-mono text-[10px] text-foreground">{{ metricsFromOutput(toolResultPayload(tc)) }}</pre>
                <UButton
                  variant="ghost"
                  color="neutral"
                  square
                  class="size-8 shrink-0 self-start rounded-none border-l border-border/80"
                  :title="t('common.copy')"
                  @pointerdown.stop
                  @click="copyText(metricsFromOutput(toolResultPayload(tc)) ?? '', copyPartKey(ti, 'metrics'))"
                >
                  <UIcon
                    v-if="copiedId === copyPartKey(ti, 'metrics')"
                    name="i-lucide-check"
                    class="size-3.5 text-green-600 dark:text-green-400"
                  />
                  <UIcon v-else name="i-lucide-copy" class="size-3.5 opacity-70" />
                </UButton>
              </div>
            </div>

            <div>
              <div class="mb-1 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                <UIcon name="i-lucide-list" class="size-3 shrink-0 opacity-80" aria-hidden="true" />
                {{ t("tools.toolResult") }}
              </div>
              <div :class="sectionBoxClass()">
                <pre class="max-h-48 min-w-0 flex-1 overflow-auto whitespace-pre-wrap break-all px-2.5 py-1.5 font-mono text-[10px] leading-relaxed text-foreground">{{ resultText(tc) }}</pre>
                <UButton
                  v-if="hasToolOut(tc)"
                  variant="ghost"
                  color="neutral"
                  square
                  class="size-8 shrink-0 self-start rounded-none border-l border-border/80"
                  :title="t('common.copy')"
                  @pointerdown.stop
                  @click="copyText(resultText(tc), copyPartKey(ti, 'result'))"
                >
                  <UIcon
                    v-if="copiedId === copyPartKey(ti, 'result')"
                    name="i-lucide-check"
                    class="size-3.5 text-green-600 dark:text-green-400"
                  />
                  <UIcon v-else name="i-lucide-copy" class="size-3.5 opacity-70" />
                </UButton>
              </div>
            </div>
          </div>
        </template>
      </UPopover>
    </div>
  </div>
</template>
