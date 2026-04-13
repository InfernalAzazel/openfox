<script setup lang="ts">
import * as monaco from "monaco-editor"
import { computed, onMounted, ref, watch } from "vue"
import { useI18n } from "vue-i18n"
import { useDark } from "@vueuse/core"
import { CodeEditor, type EditorOptions } from "monaco-editor-vue3"
import {
  getOpenFoxConfigAPI,
  putOpenFoxConfigAPI,
} from "@/api/os"
import AppPageScaffold from "@/components/AppPageScaffold.vue"
import { getAgentOsBaseUrl } from "@/composables/request"
import { useAppState } from "@/composables/store"

const { t } = useI18n()

/** 未加载完成前占位；有鉴权时进入页面会拉取服务端配置 */
const jsonText = ref("{}")

const app = useAppState()
const pageError = ref<string | null>(null)
const pageSuccess = ref<string | null>(null)
const loading = ref(false)

const isDark = useDark()
const editorTheme = computed(() => (isDark.value ? "vs-dark" : "vs"))

const editorOptions: EditorOptions = {
  fontSize: 13,
  minimap: { enabled: false },
  automaticLayout: true,
  tabSize: 2,
  wordWrap: "on",
  scrollBeyondLastLine: false,
  formatOnPaste: true,
}

/** monaco-editor-vue3 创建后不会响应 :theme 变化，需自行 setTheme */
watch(
  editorTheme,
  (t) => {
    monaco.editor.setTheme(t)
  },
  { flush: "post" },
)

function formatJson() {
  try {
    const o = JSON.parse(jsonText.value) as unknown
    jsonText.value = `${JSON.stringify(o, null, 2)}\n`
    pageError.value = null
    pageSuccess.value = null
  } catch {
    pageError.value = t("settingsConfig.invalidJsonFormat")
  }
}

/** 保存前校验：语法合法且根节点为对象 */
function parseJsonForSave(): Record<string, unknown> | null {
  const text = jsonText.value.trim()
  if (!text) {
    pageError.value = t("settingsConfig.emptyContent")
    return null
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch (e) {
    const msg = e instanceof SyntaxError ? e.message : String(e)
    pageError.value = t("settingsConfig.invalidJson", { message: msg })
    return null
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    pageError.value = t("settingsConfig.rootMustBeObject")
    return null
  }
  pageError.value = null
  return parsed as Record<string, unknown>
}

async function refreshFromServer() {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim() || undefined
  if (!base || !token) {
    pageError.value = t("settingsConfig.needLoginOs")
    return
  }
  loading.value = true
  pageError.value = null
  pageSuccess.value = null
  try {
    const r = await getOpenFoxConfigAPI(base, token)
    if (!r.ok) {
      pageError.value = t("settingsConfig.loadFailed", {
        status: r.status,
        message: r.message,
      })
      return
    }
    jsonText.value = `${JSON.stringify(r.data, null, 2)}\n`
  } finally {
    loading.value = false
  }
}

async function saveToServer() {
  const parsed = parseJsonForSave()
  if (!parsed) {
    return
  }
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim() || undefined
  if (!base || !token) {
    pageError.value = t("settingsConfig.needLogin")
    return
  }
  loading.value = true
  pageError.value = null
  pageSuccess.value = null
  try {
    const r = await putOpenFoxConfigAPI(base, token, parsed)
    if (!r.ok) {
      pageError.value = t("settingsConfig.saveFailed", {
        status: r.status,
        message: r.message,
      })
      return
    }
    pageSuccess.value = r.path
      ? t("settingsConfig.savedTo", { path: r.path })
      : t("settingsConfig.saved")
  } finally {
    loading.value = false
  }
}

async function copyToClipboard() {
  try {
    await navigator.clipboard.writeText(jsonText.value)
  } catch {
    /* 忽略 */
  }
}

onMounted(() => {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim() || undefined
  if (!base || !token) {
    return
  }
  void refreshFromServer()
})
</script>

<template>
  <AppPageScaffold
    content-class="mx-auto flex min-h-0 w-full max-w-7xl flex-1 flex-col gap-2 px-2 pb-6 md:px-4"
  >
    <div
      v-if="pageError || pageSuccess"
      class="shrink-0 space-y-1.5"
    >
      <p
        v-if="pageError"
        class="text-sm text-red-600 dark:text-red-400"
      >
        {{ pageError }}
      </p>
      <p
        v-if="pageSuccess"
        class="text-sm text-emerald-700 dark:text-emerald-400"
      >
        {{ pageSuccess }}
      </p>
    </div>

    <div
      class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-muted/40 shadow-[0_4px_20px_rgba(0,0,0,0.06)] dark:bg-card/80 dark:shadow-[0_4px_24px_rgba(0,0,0,0.35)]"
      style="min-height: min(60dvh, 32rem)"
    >
      <nav
        class="flex shrink-0 select-none flex-wrap items-stretch gap-0.5 border-b border-border bg-muted px-1 py-0.5 text-[13px] font-medium text-muted-foreground dark:bg-muted/80 dark:text-muted-foreground"
        :aria-label="t('settingsConfig.navAria')"
      >
        <button
          type="button"
          class="rounded-md px-3 py-2 transition-colors hover:bg-white/90 hover:shadow-sm dark:hover:bg-zinc-700/70 disabled:pointer-events-none disabled:opacity-40"
          :disabled="loading"
          @click="void saveToServer()"
        >
          {{ t("common.save") }}
        </button>
        <button
          type="button"
          class="rounded-md px-3 py-2 transition-colors hover:bg-white/90 hover:shadow-sm dark:hover:bg-zinc-700/70 disabled:pointer-events-none disabled:opacity-40"
          :disabled="loading"
          @click="void refreshFromServer()"
        >
          {{ t("common.refresh") }}
        </button>
        <button
          type="button"
          class="rounded-md px-3 py-2 transition-colors hover:bg-white/90 hover:shadow-sm dark:hover:bg-zinc-700/70 disabled:pointer-events-none disabled:opacity-40"
          :disabled="loading"
          @click="formatJson"
        >
          {{ t("settingsConfig.format") }}
        </button>
        <button
          type="button"
          class="rounded-md px-3 py-2 transition-colors hover:bg-white/90 hover:shadow-sm dark:hover:bg-zinc-700/70 disabled:pointer-events-none disabled:opacity-40"
          :disabled="loading"
          @click="void copyToClipboard()"
        >
          {{ t("common.copy") }}
        </button>
      </nav>
      <div class="min-h-0 flex-1 overflow-hidden bg-background">
        <CodeEditor
          v-model:value="jsonText"
          language="json"
          :theme="editorTheme"
          width="100%"
          height="100%"
          :options="editorOptions"
          @editor-did-mount="monaco.editor.setTheme(editorTheme)"
        />
      </div>
    </div>
  </AppPageScaffold>
</template>
