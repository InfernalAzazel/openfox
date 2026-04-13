<script setup lang="ts">
import { reactive } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useI18n } from "vue-i18n"
import * as z from "zod"
import type { FormSubmitEvent } from "@nuxt/ui"
import { AGENT_OS_PROXY_PREFIX, getStoredAgentOsBaseUrl } from "@/composables/request"
import { useAppState } from "@/composables/store"

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const publicBase = import.meta.env.BASE_URL
/** 开发环境默认走 Vite 代理，避免对 :7777 跨域触发 OPTIONS 失败 */
const DEFAULT_OS_BASE = import.meta.env.DEV
  ? AGENT_OS_PROXY_PREFIX
  : "http://localhost:7777"

const envBase =
  typeof import.meta.env.VITE_OS_API_BASE === "string"
    ? import.meta.env.VITE_OS_API_BASE.trim()
    : ""

const loginSchema = z.object({
  baseUrl: envBase
    ? z.string()
    : z.string().trim().min(1, t("login.errUrl")),
  token: z.string().trim().min(1, t("login.errToken")),
})

type LoginState = z.infer<typeof loginSchema>

const app = useAppState()

const state = reactive<LoginState>({
  baseUrl: (getStoredAgentOsBaseUrl() || "").trim() || DEFAULT_OS_BASE,
  token: "",
})

function onLoginSubmit(event: FormSubmitEvent<LoginState>) {
  const { baseUrl: rawBase, token: rawTok } = event.data
  const base = rawBase.trim().replace(/\/$/, "")
  const tok = rawTok.trim()
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
      class="pointer-events-none absolute inset-0 bg-linear-to-br from-default via-default to-accent/25"
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

    <UCard
      class="relative w-full max-w-md gap-0 overflow-hidden rounded-2xl border-default/70 bg-default/90 py-0 shadow-xl shadow-black/6 ring-1 ring-black/4 backdrop-blur-md dark:bg-default/80 dark:ring-white/10"
      :ui="{
        root: 'gap-0',
        header: 'flex flex-col gap-0 p-0',
        body: 'p-0',
      }"
    >
      <template #header>
        <div
          class="h-1 bg-linear-to-r from-primary/70 via-primary to-primary/70"
          aria-hidden="true"
        />
        <div class="space-y-4 px-8 pb-2 pt-8">
          <div class="flex flex-col items-center gap-3 text-center">
            <img
              :src="`${publicBase}openfox-logo-48.png`"
              alt=""
              width="48"
              height="48"
              class="size-12 rounded-xl shadow-sm ring-1 ring-default/60"
            >
            <div class="space-y-1.5">
              <p class="text-xs font-medium tracking-wide text-muted uppercase">
                {{ t("brand.name") }}
              </p>
              <h1 class="text-2xl font-semibold tracking-tight text-highlighted">
                {{ t("login.title") }}
              </h1>
              <p class="text-[0.9375rem] leading-relaxed text-muted">
                {{ t("login.subtitle") }}
              </p>
            </div>
          </div>
        </div>
      </template>

      <UForm
        :state="state"
        :schema="loginSchema"
        :validate-on="[]"
        :on-submit="onLoginSubmit"
        class="flex flex-col"
      >
        <div class="space-y-5 px-8 pb-2">
          <UFormField
            :label="t('common.url')"
            name="baseUrl"
            required
          >
            <UInput
              v-model="state.baseUrl"
              type="url"
              name="os_base_url"
              autocomplete="url"
              inputmode="url"
              :placeholder="DEFAULT_OS_BASE"
              leading-icon="i-lucide-link-2"
              size="md"
              class="w-full font-mono text-sm"
              :ui="{
                base: 'bg-default/60 border-default/80 shadow-none',
              }"
            />
          </UFormField>

          <UFormField
            :label="t('common.token')"
            name="token"
            required
          >
            <UInput
              v-model="state.token"
              type="password"
              name="token"
              autocomplete="current-password"
              :placeholder="t('login.tokenPlaceholder')"
              leading-icon="i-lucide-key-round"
              size="md"
              class="w-full font-mono text-sm"
              :ui="{
                base: 'bg-default/60 border-default/80 shadow-none',
              }"
            />
          </UFormField>
        </div>

        <div class="px-8 pb-8 pt-2">
          <UButton
            type="submit"
            size="lg"
            block
          >
            {{ t("login.submit") }}
          </UButton>
        </div>
      </UForm>
    </UCard>
  </div>
</template>

<route lang="yaml">
meta:
  layout: false
  requiresAuth: false
</route>
