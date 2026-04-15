<script setup lang="ts">
import { useDark } from "@vueuse/core"
import { computed, onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useAppState } from "@/composables/store"
import { useI18n } from "vue-i18n"

/** 与各子路由 name（vue-router/auto）及侧栏文案对齐 */
const CRUMB_I18N_KEY_BY_ROUTE_NAME: Record<string, string> = {
  "//": "routes.chat",
  "//usage": "routes.usage",
  "//sessions": "routes.sessions",
  "//scheduler": "routes.scheduler",
  "//memory": "routes.memory",
  "//knowledge": "routes.knowledge",
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
const themeIconName = computed(() =>
  isDark.value ? "i-lucide-sun" : "i-lucide-moon",
)

function toggleTheme() {
  isDark.value = !isDark.value
}

const logoutDialogOpen = ref(false)

function confirmLogout() {
  app.value.access_token = ""
  logoutDialogOpen.value = false
  void router.push("/login")
}

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

function toggleLocale() {
  locale.value = locale.value === "zh-CN" ? "en-US" : "zh-CN"
}

const navbarUi = {
  root: "sticky top-0 z-20 min-h-14 shrink-0 border-b border-border bg-background/95 px-3 backdrop-blur-md md:px-5",
}
</script>

<template>
  <UDashboardNavbar
    :toggle="false"
    :ui="navbarUi"
  >
    <template #left="{ sidebarCollapsed: navCollapsed }">
      <UDashboardSidebarToggle
        variant="ghost"
        color="neutral"
        square
        class="size-9 shrink-0 text-muted-foreground lg:hidden"
      />
      <UDashboardSidebarCollapse
        v-if="navCollapsed"
        variant="ghost"
        color="neutral"
        square
        class="hidden size-9 shrink-0 text-muted-foreground lg:inline-flex"
      />
      <UBreadcrumb
        :items="[
          { label: t('brand.name'), to: '/' },
          { label: currentPageLabel },
        ]"
        class="min-w-0 flex-1 text-sm"
      />
    </template>

    <template #right>
      <div class="flex items-center gap-0.5">
        <UTooltip
          :text="
            locale === 'zh-CN' ? t('header.languageEn') : t('header.languageZh')
          "
        >
          <UButton
            variant="ghost"
            color="neutral"
            square
            class="size-9"
            :aria-label="t('header.language')"
            @click="toggleLocale"
          >
            <span class="text-xl leading-none" aria-hidden="true">{{
              localeFlagEmoji
            }}</span>
          </UButton>
        </UTooltip>

        <UTooltip :text="t('header.theme')">
          <UButton
            variant="ghost"
            color="neutral"
            square
            class="size-9"
            :aria-label="t('header.theme')"
            @click="toggleTheme"
          >
            <UIcon :name="themeIconName" class="size-5" />
          </UButton>
        </UTooltip>

        <UTooltip :text="t('header.account')">
          <UButton
            variant="ghost"
            color="neutral"
            square
            :avatar="{
              alt: 'U',
              size: 'sm',
            }"
            @click="logoutDialogOpen = true"
          >
          </UButton>
        </UTooltip>
      </div>

      <UModal v-model:open="logoutDialogOpen">
        <template #content>
          <UCard>
            <template #header>
              <h3 class="text-lg font-semibold">
                {{ t("header.logoutTitle") }}
              </h3>
              <p class="text-sm text-muted">
                {{ t("header.logoutDescription") }}
              </p>
            </template>
            <template #footer>
              <div class="flex justify-end gap-2">
                <UButton variant="outline" @click="logoutDialogOpen = false">
                  {{ t("common.cancel") }}
                </UButton>
                <UButton color="error" @click="confirmLogout">
                  {{ t("common.confirm") }}
                </UButton>
              </div>
            </template>
          </UCard>
        </template>
      </UModal>
    </template>
  </UDashboardNavbar>
</template>
