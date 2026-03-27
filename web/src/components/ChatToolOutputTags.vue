<script setup lang="ts">
import { IconInfoCircle } from "@tabler/icons-vue"
import { computed } from "vue"
import { useI18n } from "vue-i18n"

const { t } = useI18n()

const props = defineProps<{
  text: string
}>()

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
</script>

<template>
  <div class="space-y-2">
    <p class="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
      {{ t("tools.toolOutput") }}
    </p>
    <div
      v-if="parsedEntries.kind === 'tags' && parsedEntries.tags.length"
      class="flex flex-wrap gap-2"
    >
      <div
        v-for="(e, idx) in parsedEntries.tags"
        :key="`${idx}-${e.key}`"
        class="inline-flex max-w-full items-center gap-1.5 rounded-full border border-border bg-muted px-2.5 py-1.5 pl-3 text-[11px] shadow-sm dark:border-white/10 dark:bg-secondary/80"
      >
        <span class="shrink-0 font-semibold uppercase tracking-wide text-foreground">
          {{ formatKeyLabel(e.key) }}
        </span>
        <a
          v-if="e.href"
          :href="e.href"
          class="max-w-[min(100%,22rem)] truncate font-mono text-sky-700 underline decoration-sky-700/50 underline-offset-2 dark:text-sky-400 dark:decoration-sky-400/50"
          target="_blank"
          rel="noopener noreferrer"
          :title="e.value"
        >
          {{ e.value }}
        </a>
        <span
          v-else
          class="max-w-[min(100%,22rem)] truncate font-mono text-foreground"
          :title="e.value === 'true' || e.value === 'false' ? undefined : e.value"
        >
          {{ e.value }}
        </span>
        <IconInfoCircle class="size-3.5 shrink-0 opacity-60 dark:opacity-70" aria-hidden="true" />
      </div>
    </div>
    <pre
      v-else-if="parsedEntries.kind === 'raw'"
      class="overflow-x-auto rounded-lg border border-border bg-muted/60 p-3 text-left text-[11px] leading-relaxed text-foreground dark:bg-secondary/40"
    >{{ parsedEntries.raw }}</pre>
    <p
      v-else
      class="text-xs text-muted-foreground"
    >
      {{ t("tools.empty") }}
    </p>
  </div>
</template>
