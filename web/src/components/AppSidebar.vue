<script setup lang="ts">
import type { NavigationMenuItem } from "@nuxt/ui"
import { computed } from "vue"
import { useI18n } from "vue-i18n"
import { useRoute } from "vue-router"

const { t } = useI18n()
const route = useRoute()

const openfoxLogoSrc = `${import.meta.env.BASE_URL}openfox-logo.png`
const openfoxRepoUrl = "https://github.com/InfernalAzazel/openfox"

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
        class="flex items-center justify-between gap-2 px-2 py-2.5 text-xs text-muted-foreground"
        :class="collapsed ? 'justify-center' : ''"
      >
        <span v-if="!collapsed" class="min-w-0 truncate tabular-nums">
          {{ t("sidebar.version") }}
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
