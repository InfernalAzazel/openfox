<script setup lang="ts">
import { IconMoon, IconSun } from "@tabler/icons-vue"
import { useDark } from "@vueuse/core"
import { computed, onMounted, ref, watch } from "vue"
import { RouterLink, useRoute, useRouter } from "vue-router"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { SidebarTrigger, useSidebar } from "@/components/ui/sidebar"
import { useAppState } from "@/composables/store"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { useI18n } from "vue-i18n"

/** 与各子路由 name（vue-router/auto）及侧栏文案对齐 */
const CRUMB_I18N_KEY_BY_ROUTE_NAME: Record<string, string> = {
  "//": "routes.chat",
  "//usage": "routes.usage",
  "//sessions": "routes.sessions",
  "//scheduler": "routes.scheduler",
  "//skills": "routes.skills",
  "//config": "routes.settingsConfig",
  "//docs": "routes.docs",
}

const { t, locale } = useI18n()

const route = useRoute()
const router = useRouter()
const app = useAppState()

function syncDocumentLang(code: string) {
  document.documentElement.lang = code === "zh-CN" ? "zh-CN" : "en"
}

onMounted(() => {
  syncDocumentLang(String(locale.value))
})

watch(locale, (v) => {
  const code = String(v)
  if (code === "zh-CN" || code === "en-US") {
    app.value.locale = code
  }
  syncDocumentLang(code)
})
const isDark = useDark()
const themeIcon = computed(() => (isDark.value ? IconSun : IconMoon))

function toggleTheme() {
  isDark.value = !isDark.value
}

const logoutDialogOpen = ref(false)

function confirmLogout() {
  app.value.access_token = ""
  logoutDialogOpen.value = false
  void router.push("/login")
}

const { state: sidebarState, isMobile: sidebarIsMobile } = useSidebar()
const showHeaderSidebarTrigger = computed(
  () => sidebarIsMobile.value || sidebarState.value === "collapsed",
)

const currentPageLabel = computed(() => {
  const name = String(route.name ?? "")
  const key = CRUMB_I18N_KEY_BY_ROUTE_NAME[name]
  if (key) {
    return t(key)
  }
  const last = route.matched[route.matched.length - 1]
  const n = last?.name != null ? String(last.name) : ""
  const key2 = CRUMB_I18N_KEY_BY_ROUTE_NAME[n]
  if (key2) {
    return t(key2)
  }
  const seg = route.path.split("/").filter(Boolean).pop()
  return seg || t("brand.name")
})

/** 当前语言对应国旗（简体中文 → 中国，英文 → 美国） */
const localeFlagEmoji = computed(() =>
  locale.value === "zh-CN" ? "🇨🇳" : "🇺🇸",
)
</script>

<template>
  <header
    class="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-3 border-b border-border bg-background/95 px-3 backdrop-blur-md md:px-5"
  >
    <SidebarTrigger
      v-show="showHeaderSidebarTrigger"
      class="!h-9 !w-9 shrink-0 text-muted-foreground [&_svg]:size-5"
    />
    <Breadcrumb>
      <BreadcrumbList class="text-sm text-foreground">
        <BreadcrumbItem>
          <BreadcrumbLink as-child class="font-medium">
            <RouterLink to="/">
              {{ t("brand.name") }}
            </RouterLink>
          </BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbSeparator class="text-muted-foreground/60" />
        <BreadcrumbItem>
          <BreadcrumbPage class="text-muted-foreground">
            {{ currentPageLabel }}
          </BreadcrumbPage>
        </BreadcrumbItem>
      </BreadcrumbList>
    </Breadcrumb>
    <div class="ml-auto flex items-center gap-0.5">
      <DropdownMenu>
        <DropdownMenuTrigger as-child>
          <Button
            variant="ghost"
            size="icon"
            class="size-9 text-muted-foreground [&_span]:text-xl [&_span]:leading-none"
            :aria-label="t('header.language')"
            :title="t('header.language')"
          >
            <span aria-hidden="true">{{ localeFlagEmoji }}</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" class="min-w-[11rem]">
          <DropdownMenuRadioGroup v-model="locale">
            <DropdownMenuRadioItem value="en-US" class="cursor-pointer gap-2">
              <span class="text-base leading-none" aria-hidden="true">🇺🇸</span>
              <span>{{ t("header.languageEn") }}</span>
            </DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="zh-CN" class="cursor-pointer gap-2">
              <span class="text-base leading-none" aria-hidden="true">🇨🇳</span>
              <span>{{ t("header.languageZh") }}</span>
            </DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      <Tooltip>
        <TooltipTrigger as-child>
          <Button
            variant="ghost"
            size="icon"
            class="size-9 text-muted-foreground"
            :aria-label="t('header.theme')"
            :title="t('header.theme')"
            @click="toggleTheme"
          >
            <component :is="themeIcon" class="size-5" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>{{ t("header.theme") }}</TooltipContent>
      </Tooltip>
      <Tooltip>
        <TooltipTrigger as-child>
          <Button
            variant="ghost"
            size="icon"
            class="group size-9 hover:bg-transparent focus-visible:bg-transparent"
            aria-haspopup="dialog"
            :aria-expanded="logoutDialogOpen"
            @click="logoutDialogOpen = true"
          >
            <span
              class="flex size-8 items-center justify-center rounded-full bg-muted text-xs font-medium text-foreground transition-colors group-hover:bg-accent group-hover:text-accent-foreground"
            >
              U
            </span>
          </Button>
        </TooltipTrigger>
        <TooltipContent>{{ t("header.account") }}</TooltipContent>
      </Tooltip>
    </div>

    <AlertDialog v-model:open="logoutDialogOpen">
      <AlertDialogContent class="border-border sm:rounded-xl">
        <AlertDialogHeader>
          <AlertDialogTitle class="text-foreground">
            {{ t("header.logoutTitle") }}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {{ t("header.logoutDescription") }}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel type="button">
            {{ t("common.cancel") }}
          </AlertDialogCancel>
          <Button
            type="button"
            variant="destructive"
            @click="confirmLogout"
          >
            {{ t("common.confirm") }}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </header>
</template>
