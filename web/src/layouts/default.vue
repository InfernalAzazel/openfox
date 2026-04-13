<script setup lang="ts">
/**
 * 应用主壳：Nuxt UI 仪表板布局 + 侧栏 + 顶栏 + 子路由出口。
 * @see https://ui.nuxt.com/docs/components/dashboard-group
 * @see https://github.com/JohnCampionJr/vite-plugin-vue-layouts
 */
import AppHeader from "@/components/AppHeader.vue"
import AppSidebar from "@/components/AppSidebar.vue"
import { RouterView } from "vue-router"

/** 覆盖 Nuxt UI 默认 dashboardPanel.body 的 p-4 sm:p-6，否则主区（含会话工具栏）会整体离顶栏过远 */
const panelUi = {
  root: "relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background",
  body: "!gap-0 !p-0 flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden",
}
</script>

<template>
  <UDashboardGroup
    :ui="{ base: 'fixed inset-0 z-0 flex min-h-0 overflow-hidden' }"
  >
    <!-- 侧栏：UDashboardSidebar（与 UDashboardGroup 集成），见 https://ui.nuxt.com/docs/components/dashboard-sidebar -->
    <div
      class="flex h-full min-h-0 min-w-0 w-full flex-1 overflow-hidden"
    >
      <AppSidebar />
      <UDashboardPanel :ui="panelUi">
        <template #header>
          <AppHeader />
        </template>
        <template #body>
          <!-- 与原先 SidebarInset（main）一致：整块主区交给子路由滚动 -->
          <main class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
            <RouterView />
          </main>
        </template>
      </UDashboardPanel>
    </div>
  </UDashboardGroup>
</template>
