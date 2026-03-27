<script setup lang="ts">
import { ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useI18n } from "vue-i18n"
import { KeyRound, Link2 } from "lucide-vue-next"
import { AGENT_OS_PROXY_PREFIX, getStoredAgentOsBaseUrl } from "@/composables/request"
import { useAppState } from "@/composables/store"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const publicBase = import.meta.env.BASE_URL
/** 开发环境默认走 Vite 代理，避免对 :7777 跨域触发 OPTIONS 失败 */
const DEFAULT_OS_BASE = import.meta.env.DEV
  ? AGENT_OS_PROXY_PREFIX
  : "http://localhost:7777"

const app = useAppState()
const baseUrl = ref(
  (getStoredAgentOsBaseUrl() || "").trim() || DEFAULT_OS_BASE,
)
const token = ref("")
const error = ref("")

function onSubmit() {
  const tok = token.value.trim()
  const base = baseUrl.value.trim().replace(/\/$/, "")
  if (!tok) {
    error.value = t("login.errToken")
    return
  }
  const envBase =
    typeof import.meta.env.VITE_OS_API_BASE === "string"
      ? import.meta.env.VITE_OS_API_BASE.trim()
      : ""
  if (!base && !envBase) {
    error.value = t("login.errUrl")
    return
  }
  error.value = ""
  app.value.os_base_url = base
  app.value.access_token = tok
  const next =
    typeof route.query.redirect === "string" && route.query.redirect.startsWith("/") && !route.query.redirect.startsWith("//")
      ? route.query.redirect
      : "/"
  void router.push(next)
}
</script>

<template>
  <div
    class="relative flex min-h-svh items-center justify-center overflow-hidden p-4 sm:p-6"
  >
    <!-- 背景：柔和渐变与光晕，与主题 primary / accent 呼应 -->
    <div
      class="pointer-events-none absolute inset-0 bg-linear-to-br from-background via-background to-accent/25"
      aria-hidden="true"
    />
    <div
      class="pointer-events-none absolute -left-32 top-1/4 size-112 rounded-full bg-primary/[0.07] blur-3xl"
      aria-hidden="true"
    />
    <div
      class="pointer-events-none absolute -right-40 bottom-0 size-128 rounded-full bg-accent/40 blur-3xl"
      aria-hidden="true"
    />
    <div
      class="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,oklch(0_0_0/0.03)_1px,transparent_1px),linear-gradient(to_bottom,oklch(0_0_0/0.03)_1px,transparent_1px)] bg-size-[48px_48px] mask-[radial-gradient(ellipse_80%_60%_at_50%_40%,#000_40%,transparent_100%)]"
      aria-hidden="true"
    />

    <Card
      class="relative w-full max-w-md gap-0 overflow-hidden rounded-2xl border-border/70 bg-card/90 py-0 shadow-xl shadow-black/6 ring-1 ring-black/4 backdrop-blur-md dark:ring-white/10"
    >
      <div
        class="h-1 bg-linear-to-r from-primary/70 via-primary to-primary/70"
        aria-hidden="true"
      />
      <CardHeader class="space-y-4 px-8 pb-2 pt-8">
        <div class="flex flex-col items-center gap-3 text-center">
          <img
            :src="`${publicBase}openfox-logo-48.png`"
            alt=""
            width="48"
            height="48"
            class="size-12 rounded-xl shadow-sm ring-1 ring-border/60"
          >
          <div class="space-y-1.5">
            <p class="text-muted-foreground text-xs font-medium tracking-wide uppercase">
              {{ t("brand.name") }}
            </p>
            <CardTitle class="text-2xl font-semibold tracking-tight">
              {{ t("login.title") }}
            </CardTitle>
            <CardDescription class="text-[0.9375rem] leading-relaxed">
              {{ t("login.subtitle") }}
            </CardDescription>
          </div>
        </div>
      </CardHeader>

      <form @submit.prevent="onSubmit">
        <CardContent class="space-y-5 px-8 pb-2">
          <div class="space-y-2">
            <Label
              for="os-base"
              class="text-foreground/90 text-sm font-medium"
            >
              {{ t("common.url") }}
            </Label>
            <div class="relative">
              <span
                class="text-muted-foreground pointer-events-none absolute left-3 top-1/2 z-10 -translate-y-1/2"
              >
                <Link2 class="size-4" />
              </span>
              <Input
                id="os-base"
                v-model="baseUrl"
                type="url"
                name="os_base_url"
                autocomplete="url"
                :placeholder="DEFAULT_OS_BASE"
                inputmode="url"
                class="h-10 border-border/80 bg-background/60 pl-9 font-mono text-sm shadow-none"
              />
            </div>
          </div>

          <div class="space-y-2">
            <Label
              for="token"
              class="text-foreground/90 text-sm font-medium"
            >
              {{ t("common.token") }}
            </Label>
            <div class="relative">
              <span
                class="text-muted-foreground pointer-events-none absolute left-3 top-1/2 z-10 -translate-y-1/2"
              >
                <KeyRound
                  class="size-4"
                  aria-hidden="true"
                />
              </span>
              <Input
                id="token"
                v-model="token"
                type="password"
                name="token"
                autocomplete="current-password"
                :placeholder="t('login.tokenPlaceholder')"
                :aria-invalid="error ? 'true' : undefined"
                class="h-10 border-border/80 bg-background/60 pl-9 font-mono text-sm shadow-none"
              />
            </div>
            <p
              v-if="error"
              class="text-destructive text-sm font-medium"
            >
              {{ error }}
            </p>
          </div>
        </CardContent>

        <div class="px-8 pb-8 pt-2">
          <Button
            type="submit"
            size="lg"
            class="w-full"
          >
            {{ t("login.submit") }}
          </Button>
        </div>
      </form>
    </Card>
  </div>
</template>

<route lang="yaml">
meta:
  layout: false
  requiresAuth: false
</route>
