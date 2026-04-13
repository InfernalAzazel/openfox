<script setup lang="ts">
import { computed } from "vue"
import { useI18n } from "vue-i18n"

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    text: string
    /** 与 UChatTool 一致：流式输出时触发条 shimmer */
    streaming?: boolean
    /** 是否默认展开工具输出（默认 true，与原先始终可见一致） */
    defaultOpen?: boolean
  }>(),
  {
    streaming: false,
    defaultOpen: true,
  },
)

function stripCodeFence(raw: string): string {
  let t = raw.trim()
  const fence = /^```(?:json)?\s*\n?([\s\S]*?)\n?```$/i
  const m = t.match(fence)
  if (m?.[1]) return m[1].trim()
  return t
}

function formatScalar(v: unknown): string {
  if (v === null) return "null"
  if (typeof v === "boolean" || typeof v === "number") return String(v)
  if (typeof v === "string") return v
  try {
    return JSON.stringify(v)
  } catch {
    return String(v)
  }
}

function looksLikeUrl(s: string): boolean {
  return /^https?:\/\//i.test(s) || /^wss?:\/\//i.test(s)
}

type TagEntry = { key: string; value: string; href?: string }

function flattenObject(obj: Record<string, unknown>, prefix = ""): TagEntry[] {
  const out: TagEntry[] = []
  for (const [k, v] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${k}` : k
    if (v !== null && typeof v === "object" && !Array.isArray(v)) {
      out.push(...flattenObject(v as Record<string, unknown>, path))
      continue
    }
    if (Array.isArray(v)) {
      const str = JSON.stringify(v)
      const href = undefined
      out.push({ key: path, value: str, href })
      continue
    }
    const value = formatScalar(v)
    const href = typeof value === "string" && looksLikeUrl(value) ? value : undefined
    out.push({ key: path, value, href })
  }
  return out
}

function formatKeyLabel(key: string): string {
  const last = key.includes(".") ? key.slice(key.lastIndexOf(".") + 1) : key
  return last.replace(/\s+/g, "_").toUpperCase()
}

const parsedEntries = computed(() => {
  const raw = stripCodeFence(props.text ?? "")
  if (!raw) return { kind: "empty" as const }
  try {
    const data = JSON.parse(raw) as unknown
    if (data !== null && typeof data === "object" && !Array.isArray(data)) {
      const tags = flattenObject(data as Record<string, unknown>)
      if (tags.length) return { kind: "tags" as const, tags }
      return { kind: "raw" as const, raw }
    }
    if (Array.isArray(data)) {
      const tags: TagEntry[] = data.map((v, i) => ({
        key: String(i),
        value: formatScalar(v),
        href:
          typeof v === "string" && looksLikeUrl(v)
            ? v
            : undefined,
      }))
      return { kind: "tags" as const, tags }
    }
    return {
      kind: "tags" as const,
      tags: [{ key: "VALUE", value: formatScalar(data) }],
    }
  } catch {
    return { kind: "raw" as const, raw }
  }
})

const outputSuffix = computed(() => {
  const p = parsedEntries.value
  if (p.kind !== "tags" || !p.tags.length) return undefined
  return t("tools.toolOutputFieldCount", { n: p.tags.length })
})
</script>

<template>
  <UChatTool
    class="w-full max-w-full min-w-0"
    variant="card"
    chevron="leading"
    icon="i-lucide-hammer"
    :text="t('tools.toolOutput')"
    :suffix="outputSuffix"
    :streaming="streaming"
    :default-open="defaultOpen"
  >
    <div
      v-if="parsedEntries.kind === 'tags' && parsedEntries.tags.length"
      class="flex flex-wrap gap-2"
    >
      <div
        v-for="(e, idx) in parsedEntries.tags"
        :key="`${idx}-${e.key}`"
        class="inline-flex max-w-full items-center gap-1.5 rounded-full border border-default bg-elevated px-2.5 py-1.5 pl-3 text-[11px] shadow-sm"
      >
        <span class="shrink-0 font-semibold uppercase tracking-wide text-default">
          {{ formatKeyLabel(e.key) }}
        </span>
        <a
          v-if="e.href"
          :href="e.href"
          class="max-w-[min(100%,22rem)] truncate font-mono text-primary underline decoration-primary/50 underline-offset-2"
          target="_blank"
          rel="noopener noreferrer"
          :title="e.value"
        >
          {{ e.value }}
        </a>
        <span
          v-else
          class="max-w-[min(100%,22rem)] truncate font-mono text-default"
          :title="e.value === 'true' || e.value === 'false' ? undefined : e.value"
        >
          {{ e.value }}
        </span>
        <UIcon name="i-lucide-info" class="size-3.5 shrink-0 opacity-60" aria-hidden="true" />
      </div>
    </div>
    <pre
      v-else-if="parsedEntries.kind === 'raw'"
      class="overflow-x-auto rounded-lg border border-default bg-muted/50 p-3 text-left text-[11px] leading-relaxed text-default"
    >{{ parsedEntries.raw }}</pre>
    <p
      v-else
      class="text-xs text-dimmed"
    >
      {{ t("tools.empty") }}
    </p>
  </UChatTool>
</template>
