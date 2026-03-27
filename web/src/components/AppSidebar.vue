<script setup lang="ts">
import {
  IconBolt,
  IconBook,
  IconChartBar,
  IconChevronDown,
  IconFileText,
  IconMessage,
  IconSettings,
  IconSparkles,
} from "@tabler/icons-vue"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar"
import { PanelLeft, X } from "lucide-vue-next"
import { computed, ref } from "vue"
import { useI18n } from "vue-i18n"
import { RouterLink, useRoute } from "vue-router"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const { t } = useI18n()
const { state, toggleSidebar, isMobile } = useSidebar()
const route = useRoute()

const openChat = ref(true)
const openControl = ref(true)
const openSettings = ref(true)

const controlNav = computed(() => [
  { titleKey: "routes.sessions", icon: IconFileText, to: "/sessions" },
  { titleKey: "routes.usage", icon: IconChartBar, to: "/usage" },
  { titleKey: "routes.skills", icon: IconBolt, to: "/skills" },
  { titleKey: "routes.scheduler", icon: IconSparkles, to: "/scheduler" },
] as const)

const settingsNav = computed(() => [
  { titleKey: "routes.settingsConfig", icon: IconSettings, to: "/config" },
] as const)

const sidebarTitleControl = computed(() => t("sidebar.control"))
const sidebarChat = computed(() => t("sidebar.chat"))
const sidebarSettings = computed(() => t("sidebar.settings"))
const sidebarDocs = computed(() => t("sidebar.docs"))
const sidebarDocsTooltip = computed(() => t("sidebar.docsTooltip"))
const closeSidebarLabel = computed(() => t("sidebar.closeSidebar"))
const collapseSidebarLabel = computed(() => t("sidebar.collapseSidebar"))

const groupTriggerClass = cn(
  "flex h-9 w-full items-center justify-between rounded-md px-2 text-left text-[11px] font-medium uppercase tracking-wide text-muted-foreground outline-none ring-sidebar-ring transition-colors hover:bg-sidebar-accent/80 hover:text-sidebar-foreground focus-visible:ring-2",
  "group-data-[collapsible=icon]:hidden",
)

const openfoxRepoUrl = "https://github.com/InfernalAzazel/openfox"
/** 透明底 PNG，96×96 源；在侧栏圆形容器内约 32px 显示 */
const openfoxLogoSrc = `${import.meta.env.BASE_URL}openfox-logo.png`
</script>

<template>
  <!-- icon：收起时为窄条，仅显示图标 + tooltip；不要用 offcanvas（会整块滑出视窗） -->
  <Sidebar
    collapsible="icon"
    class="border-r border-sidebar-border bg-sidebar"
  >
    <SidebarHeader
      class="border-b border-sidebar-border px-2 py-3 group-data-[collapsible=icon]:px-1 group-data-[collapsible=icon]:py-2"
    >
      <div
        class="flex items-center gap-2 px-1 group-data-[collapsible=icon]:flex-col group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:gap-2 group-data-[collapsible=icon]:px-0"
      >
        <div
          class="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-full bg-card shadow-sm ring-1 ring-border"
          aria-hidden="true"
        >
          <img
            :src="openfoxLogoSrc"
            width="32"
            height="32"
            alt=""
            class="size-8 object-contain"
            decoding="async"
          />
        </div>
        <div class="min-w-0 flex-1 leading-tight group-data-[collapsible=icon]:hidden">
          <p class="text-[10px] font-medium text-muted-foreground">
            {{ sidebarTitleControl }}
          </p>
          <p class="truncate text-sm font-semibold text-sidebar-foreground">
            {{ t("brand.name") }}
          </p>
        </div>
        <Button
          v-if="state === 'expanded' || isMobile"
          data-sidebar="trigger"
          data-slot="sidebar-trigger"
          variant="ghost"
          size="icon"
          class="size-8 shrink-0 rounded-full border border-border bg-card shadow-sm"
          :title="isMobile ? closeSidebarLabel : collapseSidebarLabel"
          @click="toggleSidebar"
        >
          <PanelLeft v-if="!isMobile" class="size-4" aria-hidden="true" />
          <X v-else class="size-4" aria-hidden="true" />
          <span class="sr-only">{{ isMobile ? closeSidebarLabel : collapseSidebarLabel }}</span>
        </Button>
      </div>
    </SidebarHeader>

    <SidebarContent class="gap-0 px-1.5 py-2">
      <!-- 聊天 -->
      <Collapsible v-model:open="openChat">
        <SidebarGroup class="p-0">
          <CollapsibleTrigger :class="groupTriggerClass">
            <span>{{ sidebarChat }}</span>
            <IconChevronDown
              class="size-4 shrink-0 text-muted-foreground/80 transition-transform duration-200"
              :class="openChat ? 'rotate-180' : ''"
            />
          </CollapsibleTrigger>
          <CollapsibleContent>
            <SidebarGroupContent class="pt-0.5">
              <SidebarMenu>
                <SidebarMenuItem>
                  <SidebarMenuButton
                    as-child
                    :is-active="route.path === '/'"
                    :tooltip="sidebarChat"
                    class="text-foreground data-[active=true]:border data-[active=true]:border-primary/25 data-[active=true]:bg-accent data-[active=true]:shadow-sm data-[active=true]:text-primary dark:data-[active=true]:border-primary/35"
                  >
                    <RouterLink to="/">
                      <IconMessage
                        class="size-4 shrink-0 transition-colors"
                        :class="
                          route.path === '/'
                            ? 'text-primary'
                            : 'text-muted-foreground opacity-80'
                        "
                      />
                      <span>{{ sidebarChat }}</span>
                    </RouterLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarGroupContent>
          </CollapsibleContent>
        </SidebarGroup>
      </Collapsible>

      <SidebarSeparator class="my-2 bg-sidebar-border" />

      <!-- 控制 -->
      <Collapsible v-model:open="openControl">
        <SidebarGroup class="p-0">
          <CollapsibleTrigger :class="groupTriggerClass">
            <span>{{ sidebarTitleControl }}</span>
            <IconChevronDown
              class="size-4 shrink-0 text-muted-foreground/80 transition-transform duration-200"
              :class="openControl ? 'rotate-180' : ''"
            />
          </CollapsibleTrigger>
          <CollapsibleContent>
            <SidebarGroupContent class="pt-0.5">
              <SidebarMenu>
                <SidebarMenuItem v-for="item in controlNav" :key="item.to">
                  <SidebarMenuButton
                    as-child
                    :is-active="route.path === item.to"
                    :tooltip="t(item.titleKey)"
                    class="text-muted-foreground hover:text-foreground data-[active=true]:border data-[active=true]:border-primary/25 data-[active=true]:bg-accent data-[active=true]:text-primary dark:data-[active=true]:border-primary/35"
                  >
                    <RouterLink :to="item.to">
                      <component :is="item.icon" class="size-4 opacity-80" />
                      <span>{{ t(item.titleKey) }}</span>
                    </RouterLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarGroupContent>
          </CollapsibleContent>
        </SidebarGroup>
      </Collapsible>

      <SidebarSeparator class="my-2 bg-sidebar-border" />

      <!-- 设置 -->
      <Collapsible v-model:open="openSettings">
        <SidebarGroup class="p-0">
          <CollapsibleTrigger :class="groupTriggerClass">
            <span>{{ sidebarSettings }}</span>
            <IconChevronDown
              class="size-4 shrink-0 text-muted-foreground/80 transition-transform duration-200"
              :class="openSettings ? 'rotate-180' : ''"
            />
          </CollapsibleTrigger>
          <CollapsibleContent>
            <SidebarGroupContent class="pt-0.5">
              <SidebarMenu>
                <SidebarMenuItem v-for="item in settingsNav" :key="item.to">
                  <SidebarMenuButton
                    as-child
                    :is-active="route.path === item.to"
                    :tooltip="t(item.titleKey)"
                    class="text-muted-foreground hover:text-foreground data-[active=true]:border data-[active=true]:border-primary/25 data-[active=true]:bg-accent data-[active=true]:text-primary dark:data-[active=true]:border-primary/35"
                  >
                    <RouterLink :to="item.to">
                      <component :is="item.icon" class="size-4 opacity-80" />
                      <span>{{ t(item.titleKey) }}</span>
                    </RouterLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarGroupContent>
          </CollapsibleContent>
        </SidebarGroup>
      </Collapsible>
    </SidebarContent>

    <SidebarFooter class="border-t border-sidebar-border px-2 py-2">
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton
            as-child
            :is-active="false"
            :tooltip="sidebarDocsTooltip"
            class="text-muted-foreground hover:text-foreground"
          >
            <a
              :href="openfoxRepoUrl"
              target="_blank"
              rel="noopener noreferrer"
            >
              <IconBook class="size-4 opacity-80" />
              <span>{{ sidebarDocs }}</span>
            </a>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
      <div
        class="mt-2 flex items-center justify-between gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground shadow-sm group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:border-0 group-data-[collapsible=icon]:bg-transparent group-data-[collapsible=icon]:p-0 group-data-[collapsible=icon]:shadow-none"
      >
        <span class="truncate group-data-[collapsible=icon]:hidden">
          {{ t("sidebar.version") }}
        </span>
        <span
          class="size-2 shrink-0 rounded-full bg-emerald-500 shadow-sm group-data-[collapsible=icon]:size-2.5"
          :title="t('common.online')"
        />
      </div>
    </SidebarFooter>

    <SidebarRail />
  </Sidebar>
</template>
