<script setup lang="ts">
/**
 * 应用主壳：侧栏 + 顶栏 + 子路由出口（`default.vue` 为插件默认布局文件名）。
 * @see https://github.com/JohnCampionJr/vite-plugin-vue-layouts
 */
import AppHeader from "@/components/AppHeader.vue"
import AppSidebar from "@/components/AppSidebar.vue"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { RouterView } from "vue-router"
</script>

<template>
  <SidebarProvider>
    <AppSidebar />
    <SidebarInset class="flex min-h-0 flex-1 flex-col overflow-hidden bg-background">
      <AppHeader />
      <div class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <RouterView />
      </div>
    </SidebarInset>
  </SidebarProvider>
</template>
