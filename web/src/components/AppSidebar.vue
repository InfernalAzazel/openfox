<script setup lang="ts">
import type { NavigationMenuItem } from "@nuxt/ui"
import { computed, onMounted, onUnmounted, ref, watch } from "vue"
import { useI18n } from "vue-i18n"
import { useRoute } from "vue-router"
import { getOpenFoxVersionAPI } from "@/api/os"
import { getAgentOsBaseUrl } from "@/composables/request"
import { useAppState } from "@/composables/store"

const { t } = useI18n()
const route = useRoute()
const app = useAppState()

const openfoxLogoSrc = `${import.meta.env.BASE_URL}openfox-logo.png`
const openfoxRepoUrl = "https://github.com/InfernalAzazel/openfox"
const openfoxTagsUrl = "https://github.com/InfernalAzazel/openfox/tags"
const githubTagsApi = "https://api.github.com/repos/InfernalAzazel/openfox/tags?per_page=1"
const jsdelivrTagsApi = "https://data.jsdelivr.com/v1/package/gh/InfernalAzazel/openfox"
const backendVersion = ref("")
const latestTagVersion = ref("")
const latestTagFetchFailed = ref(false)

const versionText = computed(() =>
  backendVersion.value
    ? `${t("sidebar.version")} ${backendVersion.value}`
    : t("sidebar.version"),
)

function parseTagVersion(raw: string): { y: number; m: number; d: number; patch: number } | null {
  const m = raw.trim().match(/^v?(\d+)\.(\d+)\.(\d+)(?:-(\d+))?$/)
  if (!m) return null
  return {
    y: Number.parseInt(m[1]!, 10),
    m: Number.parseInt(m[2]!, 10),
    d: Number.parseInt(m[3]!, 10),
    patch: Number.parseInt(m[4] ?? "0", 10),
  }
}

function compareTagVersions(aRaw: string, bRaw: string): number {
  const a = parseTagVersion(aRaw)
  const b = parseTagVersion(bRaw)
  if (a && b) {
    if (a.y !== b.y) return a.y - b.y
    if (a.m !== b.m) return a.m - b.m
    if (a.d !== b.d) return a.d - b.d
    return a.patch - b.patch
  }
  return aRaw.localeCompare(bRaw, undefined, { numeric: true, sensitivity: "base" })
}

function parseBackendVersion(raw: string): { y: number; m: number; d: number; patch: number; isDev: boolean } | null {
  const m = raw.trim().match(/^(\d+)\.(\d+)\.(\d+)(?:\.post(\d+))?(?:\.dev(\d+))?.*$/)
  if (!m) return null
  return {
    y: Number.parseInt(m[1]!, 10),
    m: Number.parseInt(m[2]!, 10),
    d: Number.parseInt(m[3]!, 10),
    patch: Number.parseInt(m[4] ?? "0", 10),
    isDev: !!m[5],
  }
}

const hasNewVersion = computed(() => {
  const latestRaw = latestTagVersion.value.trim()
  const currentRaw = backendVersion.value.trim()
  if (!latestRaw || !currentRaw) return false
  const latest = parseTagVersion(latestRaw)
  const current = parseBackendVersion(currentRaw)
  if (latest && current) {
    if (latest.y !== current.y) return latest.y > current.y
    if (latest.m !== current.m) return latest.m > current.m
    if (latest.d !== current.d) return latest.d > current.d
    if (latest.patch !== current.patch) return latest.patch > current.patch
    // 同 patch 下，release tag 视为高于后端 dev 版本
    return current.isDev
  }
  const latestNoV = latestRaw.replace(/^v/i, "")
  return !currentRaw.includes(latestRaw) && !currentRaw.includes(latestNoV)
})

async function refreshVersion() {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim()
  if (!base || !token) {
    backendVersion.value = ""
    return
  }
  const res = await getOpenFoxVersionAPI(base, token)
  backendVersion.value = res.ok ? res.version : ""
}

async function refreshLatestTagVersion() {
  latestTagFetchFailed.value = false
  const setLatestFromList = (tags: string[]) => {
    const candidates = tags
      .map((x) => x.trim())
      .filter(Boolean)
    if (!candidates.length) {
      latestTagVersion.value = ""
      latestTagFetchFailed.value = true
      return
    }
    candidates.sort((a, b) => compareTagVersions(b, a))
    const top = candidates[0]!
    latestTagVersion.value = top.startsWith("v") ? top : `v${top}`
  }

  try {
    const githubRes = await fetch(githubTagsApi, { method: "GET" })
    if (githubRes.ok) {
      const data = (await githubRes.json()) as Array<{ name?: unknown }>
      const tags = data
        .map((x) => (typeof x.name === "string" ? x.name : ""))
        .filter(Boolean)
      if (tags.length) {
        setLatestFromList(tags)
        return
      }
    }
  } catch {
    // fallback below
  }

  try {
    const jsdRes = await fetch(jsdelivrTagsApi, { method: "GET" })
    if (!jsdRes.ok) {
      latestTagVersion.value = ""
      latestTagFetchFailed.value = true
      return
    }
    const data = (await jsdRes.json()) as { versions?: unknown }
    const versions = Array.isArray(data.versions)
      ? data.versions.filter((v): v is string => typeof v === "string")
      : []
    setLatestFromList(versions)
  } catch {
    latestTagVersion.value = ""
    latestTagFetchFailed.value = true
  }
}

onMounted(() => {
  void refreshVersion()
  void refreshLatestTagVersion()
  window.addEventListener("focus", onWindowFocus)
})

onUnmounted(() => {
  window.removeEventListener("focus", onWindowFocus)
})

watch(
  () => [app.value.access_token, app.value.os_base_url] as const,
  () => {
    void refreshVersion()
    void refreshLatestTagVersion()
  },
)

function onWindowFocus() {
  void refreshLatestTagVersion()
}

watch(
  () => route.fullPath,
  () => {
    void refreshLatestTagVersion()
  },
)

const items = computed<NavigationMenuItem[][]>(() => [
  [
    { label: t("sidebar.sectionChat"), type: "label" },
    {
      label: t("sidebar.chat"),
      icon: "i-lucide-message-square",
      to: "/",
      active: route.path === "/",
    },
    { label: t("sidebar.sectionControl"), type: "label" },
    {
      label: t("routes.sessions"),
      icon: "i-lucide-file-text",
      to: "/sessions",
      active: route.path === "/sessions",
    },
    {
      label: t("routes.memory"),
      icon: "i-lucide-brain",
      to: "/memory",
      active: route.path === "/memory",
    },
    {
      label: t("routes.knowledge"),
      icon: "i-lucide-book-open-text",
      to: "/knowledge",
      active: route.path === "/knowledge",
    },
    {
      label: t("routes.usage"),
      icon: "i-lucide-chart-bar",
      to: "/usage",
      active: route.path === "/usage",
    },
    {
      label: t("routes.skills"),
      icon: "i-lucide-zap",
      to: "/skills",
      active: route.path === "/skills",
    },
    {
      label: t("routes.traces"),
      icon: "i-lucide-workflow",
      to: "/traces",
      active: route.path === "/traces",
    },
    {
      label: t("routes.evals"),
      icon: "i-lucide-target",
      to: "/evals",
      active: route.path === "/evals",
    },
    {
      label: t("routes.scheduler"),
      icon: "i-lucide-sparkles",
      to: "/scheduler",
      active: route.path === "/scheduler",
    },
    { label: t("sidebar.sectionSystem"), type: "label" },
    {
      label: t("routes.settingsConfig"),
      icon: "i-lucide-settings",
      to: "/config",
      active: route.path === "/config",
    },
  ],
  [
    {
      label: t("sidebar.docs"),
      icon: "i-lucide-book-open",
      to: openfoxRepoUrl,
      target: "_blank",
      rel: "noopener noreferrer",
      tooltip: { text: t("sidebar.docsTooltip") },
    },
  ],
])
</script>

<template>
  <UDashboardSidebar
    collapsible
    resizable
    :ui="{
      root: 'border-sidebar-border bg-sidebar',
      header:
        'border-b border-sidebar-border/80 bg-sidebar/95 backdrop-blur-sm supports-[backdrop-filter]:bg-sidebar/80',
      body: 'flex min-h-0 flex-1 flex-col gap-1 bg-sidebar !py-3',
      footer: 'border-t border-sidebar-border/80 bg-sidebar',
    }"
  >
    <template #header="{ collapsed }">
      <div
        class="flex items-center gap-3"
        :class="collapsed ? 'w-full justify-center gap-0' : ''"
      >
        <div
          class="grid size-10 shrink-0 place-items-center overflow-hidden rounded-xl bg-card shadow-sm ring-1 ring-inset ring-primary/10"
          aria-hidden="true"
        >
          <img
            :src="openfoxLogoSrc"
            width="32"
            height="32"
            alt=""
            class="block size-8 max-h-full max-w-full object-contain object-center select-none"
            decoding="async"
          >
        </div>
        <div v-if="!collapsed" class="min-w-0 flex-1 leading-tight">
          <p
            class="text-[11px] font-medium uppercase tracking-wider text-muted-foreground"
          >
            {{ t("sidebar.control") }}
          </p>
          <p
            class="truncate text-[15px] font-semibold tracking-tight text-sidebar-foreground"
          >
            {{ t("brand.name") }}
          </p>
        </div>
      </div>
    </template>

    <template #default="{ collapsed }">
      <UNavigationMenu
        :collapsed="collapsed"
        :items="items[0]"
        orientation="vertical"
        variant="link"
        color="primary"
        highlight
        tooltip
        popover

      />

      <UNavigationMenu
        :collapsed="collapsed"
        :items="items[1]"
        orientation="vertical"
        variant="link"
        color="neutral"
        tooltip
        external-icon="i-lucide-arrow-up-right"
        class="mt-auto"
      />
    </template>

    <template #footer="{ collapsed }">
      <div
        role="status"
        :aria-label="t('sidebar.footerNav')"
        class="flex min-w-0 items-center justify-between gap-2 px-2 py-2.5 text-xs text-muted-foreground"
        :class="collapsed ? 'justify-center' : ''"
      >
        <span
          v-if="!collapsed"
          class="block min-w-0 flex-1"
          :title="versionText"
        >
          <span class="block truncate tabular-nums">
            {{ versionText }}
          </span>
          <a
            v-if="hasNewVersion && latestTagVersion"
            :href="openfoxTagsUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="block truncate text-[11px] text-amber-600 hover:text-amber-500 dark:text-amber-400 dark:hover:text-amber-300"
            :title="t('sidebar.updateAvailable', { tag: latestTagVersion })"
          >
            {{ t("sidebar.updateAvailable", { tag: latestTagVersion }) }}
          </a>
          <a
            v-else-if="latestTagFetchFailed"
            :href="openfoxTagsUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="block truncate text-[11px] text-muted-foreground hover:text-foreground"
            :title="t('sidebar.checkUpdate')"
          >
            {{ t("sidebar.checkUpdate") }}
          </a>
        </span>
        <span
          class="inline-flex shrink-0 rounded-full bg-emerald-500/90 shadow-sm ring-2 ring-sidebar"
          :class="collapsed ? 'size-2.5' : 'size-2'"
          :title="t('common.online')"
        />
      </div>
    </template>
  </UDashboardSidebar>
</template>
