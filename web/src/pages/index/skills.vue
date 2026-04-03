<script setup lang="ts">
import { createColumnHelper } from "@tanstack/vue-table"
import { computed, h, nextTick, onMounted, ref } from "vue"
import { useI18n } from "vue-i18n"
import {
  deleteOpenFoxSkillAPI,
  listOpenFoxSkillsAPI,
  patchOpenFoxSkillActivateAPI,
  replaceOpenFoxSkillAPI,
  uploadOpenFoxSkillAPI,
  type OpenFoxSkillInfo,
} from "@/api/os"
import AppPageScaffold from "@/components/AppPageScaffold.vue"
import { DataTable } from "@/components/ui/data-table"
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
import { Switch } from "@/components/ui/switch"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { getAgentOsBaseUrl } from "@/composables/request"
import { useAppState } from "@/composables/store"
import { cn } from "@/lib/utils"
import { MoreVertical, RefreshCw } from "lucide-vue-next"

const { t, locale } = useI18n()
const app = useAppState()

const items = ref<OpenFoxSkillInfo[]>([])
const loading = ref(false)
const pageError = ref<string | null>(null)
const pageSuccess = ref<string | null>(null)
const uploading = ref(false)
const replacingName = ref<string | null>(null)
const deletingName = ref<string | null>(null)
const deleteConfirmOpen = ref(false)
const pendingDeleteName = ref<string | null>(null)
const togglingFolder = ref<string | null>(null)

/** 磁盘上的技能目录名（可能与 SKILL.md 的 name 不同，例如停用时常以「-」结尾） */
function skillDiskFolder(s: OpenFoxSkillInfo): string {
  const normalized = s.path.replace(/\\/g, "/")
  const parts = normalized.split("/").filter(Boolean)
  return parts[parts.length - 1] || s.name
}

function skillRowId(row: OpenFoxSkillInfo) {
  return row.path
}

/** 操作列：悬停展开下拉（单行仅一个菜单打开） */
const openActionsForName = ref<string | null>(null)
let actionsHoverCloseTimer: ReturnType<typeof setTimeout> | null = null
const ACTIONS_HOVER_CLOSE_MS = 200

function clearActionsHoverCloseTimer() {
  if (actionsHoverCloseTimer) {
    clearTimeout(actionsHoverCloseTimer)
    actionsHoverCloseTimer = null
  }
}

function scheduleActionsMenuClose() {
  clearActionsHoverCloseTimer()
  actionsHoverCloseTimer = setTimeout(() => {
    openActionsForName.value = null
  }, ACTIONS_HOVER_CLOSE_MS)
}

function showActionsMenu(name: string) {
  clearActionsHoverCloseTimer()
  openActionsForName.value = name
}

function onActionsMenuOpenChange(open: boolean) {
  if (!open) {
    openActionsForName.value = null
    clearActionsHoverCloseTimer()
  }
}

function onActionsContentPointerEnter(name: string) {
  clearActionsHoverCloseTimer()
  openActionsForName.value = name
}

const fileUploadRef = ref<HTMLInputElement | null>(null)
const fileReplaceRef = ref<HTMLInputElement | null>(null)
const replaceTargetName = ref<string | null>(null)

const hasOsAuth = computed(() => {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim()
  return !!(base && token)
})

async function loadList(opts?: { silent?: boolean }) {
  const silent = opts?.silent ?? false
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim() || undefined
  if (!base || !token) {
    pageError.value = t("skills.needLoginOs")
    return
  }
  if (!silent) {
    loading.value = true
  }
  pageError.value = null
  try {
    const r = await listOpenFoxSkillsAPI(base, token)
    if (!r.ok) {
      pageError.value = t("skills.loadFailed", {
        status: r.status,
        message: r.message,
      })
      return
    }
    items.value = r.data
    await nextTick()
  } finally {
    if (!silent) {
      loading.value = false
    }
  }
}

async function onToggleActivate(diskFolder: string, activate: boolean) {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim() || undefined
  if (!base || !token) {
    pageError.value = t("skills.needLogin")
    return
  }
  const row = items.value.find((s) => skillDiskFolder(s) === diskFolder)
  if (row && row.activate === activate) {
    return
  }
  togglingFolder.value = diskFolder
  pageError.value = null
  pageSuccess.value = null
  try {
    const r = await patchOpenFoxSkillActivateAPI(base, token, diskFolder, activate)
    if (!r.ok) {
      pageError.value = t("skills.toggleFailed", {
        status: r.status,
        message: r.message,
      })
      return
    }
    pageSuccess.value = t("skills.activateUpdated", { name: r.skill.name })
    // 必须整表替换 data：原地 splice 往往不触发 @tanstack/vue-table 与表格状态同步，
    // 界面会停在旧行；silent 避免 loading 造成闪烁。
    await loadList({ silent: true })
  } finally {
    togglingFolder.value = null
  }
}

const columnHelper = createColumnHelper<OpenFoxSkillInfo>()

const tableColumns = computed(() => {
  void locale.value
  return [
  columnHelper.accessor("activate", {
    header: t("skills.colActivate"),
    // 开关在模板中渲染，直接绑定 row.original，避免 FlexRender/非响应式 table 导致陈旧
    cell: () => null,
  }),
  columnHelper.accessor("name", {
    header: t("skills.colName"),
    cell: (ctx) =>
      h(
        "span",
        {
          class:
            "block min-w-0 max-w-full break-words line-clamp-2 wrap-break-word font-mono text-sm font-medium text-foreground",
        },
        ctx.getValue(),
      ),
  }),
  columnHelper.accessor("description", {
    header: t("skills.colDescription"),
    cell: (ctx) => {
      const text = String(ctx.getValue() ?? "")
      return h(
        "span",
        {
          class:
            "block min-w-0 max-w-full truncate text-sm text-foreground",
          title: text,
        },
        text,
      )
    },
  }),
  columnHelper.accessor("path", {
    header: t("skills.colPath"),
    cell: (ctx) => {
      const p = ctx.getValue()
      return h(
        "span",
        {
          class:
            "block min-w-0 max-w-full truncate font-mono text-sm text-foreground",
          title: p,
        },
        p,
      )
    },
  }),
  columnHelper.accessor("license", {
    header: t("skills.colLicense"),
    cell: (ctx) => {
      const v = ctx.getValue()
      const s = typeof v === "string" ? v.trim() : ""
      return h(
        "span",
        { class: "whitespace-nowrap text-sm text-muted-foreground" },
        s || t("skills.emptyCell"),
      )
    },
  }),
  columnHelper.display({
    id: "actions",
    header: () =>
      h(
        "span",
        { class: "block w-full text-right font-medium" },
        t("skills.colActions"),
      ),
    cell: () => null,
  }),
]
})

function triggerUpload() {
  pageSuccess.value = null
  fileUploadRef.value?.click()
}

function triggerReplace(name: string) {
  pageSuccess.value = null
  replaceTargetName.value = name
  fileReplaceRef.value?.click()
}

async function onUploadFile(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ""
  if (!file) return
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim() || undefined
  if (!base || !token) {
    pageError.value = t("skills.needLogin")
    return
  }
  uploading.value = true
  pageError.value = null
  try {
    const r = await uploadOpenFoxSkillAPI(base, token, file)
    if (!r.ok) {
      pageError.value =
        r.status === 409
          ? r.message
          : t("skills.uploadFailed", { status: r.status, message: r.message })
      return
    }
    pageSuccess.value = t("skills.installed", { name: r.skill.name })
    await loadList()
  } finally {
    uploading.value = false
  }
}

async function onReplaceFile(ev: Event) {
  const name = replaceTargetName.value
  replaceTargetName.value = null
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ""
  if (!file || !name) return
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim() || undefined
  if (!base || !token) {
    pageError.value = t("skills.needLogin")
    return
  }
  replacingName.value = name
  pageError.value = null
  try {
    const r = await replaceOpenFoxSkillAPI(base, token, name, file)
    if (!r.ok) {
      pageError.value = t("skills.updateFailed", {
        status: r.status,
        message: r.message,
      })
      return
    }
    pageSuccess.value = t("skills.updated", { name: r.skill.name })
    await loadList()
  } finally {
    replacingName.value = null
  }
}

function requestDelete(name: string) {
  pendingDeleteName.value = name
  deleteConfirmOpen.value = true
}

async function confirmDelete() {
  const name = pendingDeleteName.value
  pendingDeleteName.value = null
  deleteConfirmOpen.value = false
  if (!name) return
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim() || undefined
  if (!base || !token) {
    pageError.value = t("skills.needLogin")
    return
  }
  deletingName.value = name
  pageError.value = null
  pageSuccess.value = null
  try {
    const r = await deleteOpenFoxSkillAPI(base, token, name)
    if (!r.ok) {
      pageError.value = t("skills.deleteFailed", {
        status: r.status,
        message: r.message,
      })
      return
    }
    pageSuccess.value = t("skills.deleted", { name })
    await loadList()
  } finally {
    deletingName.value = null
  }
}

function headerClass(columnId: string) {
  const base =
    "text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
  if (columnId === "activate") {
    return cn("w-16 shrink-0", base)
  }
  if (columnId === "name") {
    return cn("w-[10rem] min-w-0 shrink-0 font-mono", base)
  }
  if (columnId === "description") {
    return cn("min-w-0 w-[38%]", base)
  }
  if (columnId === "path") {
    return cn("min-w-0 w-[34%] font-mono", base)
  }
  if (columnId === "license") {
    return cn("w-24 shrink-0", base)
  }
  if (columnId === "actions") {
    return cn("w-14 shrink-0 pr-2 text-right", base)
  }
  return base
}

function cellClass(columnId: string) {
  if (columnId === "actions") {
    return "min-w-0 py-3 pl-2 text-right align-top"
  }
  if (columnId === "activate") {
    return "w-16 shrink-0 py-3 align-top"
  }
  return "min-w-0 py-3 align-top"
}

onMounted(() => {
  if (hasOsAuth.value) {
    void loadList()
  } else {
    pageError.value = t("skills.needLoginOs")
  }
})
</script>

<template>
  <AppPageScaffold content-class="flex min-h-0 flex-col">
    <div class="flex min-h-0 w-full flex-1 flex-col gap-4">
      <p
        v-if="pageError"
        class="shrink-0 text-sm text-red-600 dark:text-red-400"
      >
        {{ pageError }}
      </p>
      <p
        v-else-if="pageSuccess"
        class="shrink-0 text-sm text-emerald-700 dark:text-emerald-400"
      >
        {{ pageSuccess }}
      </p>
      <p
        v-else-if="!hasOsAuth"
        class="shrink-0 text-sm text-muted-foreground"
      >
        {{ t("skills.manageHint") }}
      </p>

      <div class="min-w-0 flex-1">
        <div
          class="rounded-xl border border-border bg-card shadow-sm"
        >
          <div
            class="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3"
          >
            <span
              class="text-left text-xs font-normal tracking-normal text-muted-foreground"
            >
              {{
                loading && !items.length
                  ? t("common.loading")
                  : t("common.itemsInTable", { count: items.length })
              }}
            </span>
            <div class="flex items-center gap-2">
              <input
                ref="fileUploadRef"
                type="file"
                accept=".zip,application/zip"
                class="sr-only"
                :aria-label="t('skills.uploadZipAria')"
                @change="onUploadFile"
              >
              <input
                ref="fileReplaceRef"
                type="file"
                accept=".zip,application/zip"
                class="sr-only"
                :aria-label="t('skills.uploadZipAria')"
                @change="onReplaceFile"
              >
              <Tooltip>
                <TooltipTrigger as-child>
                  <Button
                    variant="outline"
                    size="sm"
                    type="button"
                    class="h-9 rounded-lg border-border bg-muted/50 text-xs font-semibold uppercase tracking-wide text-foreground dark:bg-muted/30"
                    :disabled="!hasOsAuth || uploading"
                    @click="triggerUpload"
                  >
                    {{ uploading ? t("skills.uploading") : t("skills.createSkill") }}
                  </Button>
                </TooltipTrigger>
                <TooltipContent class="max-w-xs">
                  {{ t("skills.uploadZipHint") }}
                </TooltipContent>
              </Tooltip>
              <Button
                variant="outline"
                size="icon"
                type="button"
                class="h-9 w-9 shrink-0 rounded-lg border-border bg-muted/50 text-foreground dark:bg-muted/30"
                :title="t('skills.refreshList')"
                :disabled="!hasOsAuth || loading"
                @click="void loadList()"
              >
                <RefreshCw
                  class="size-4 opacity-70"
                  :class="loading ? 'animate-spin' : ''"
                  aria-hidden="true"
                />
                <span class="sr-only">{{ t("common.refresh") }}</span>
              </Button>
            </div>
          </div>

          <div class="overflow-x-auto">
            <DataTable
              :columns="tableColumns"
              :data="items"
              table-class="table-fixed"
              :header-class="headerClass"
              :cell-class="cellClass"
              :get-row-id="skillRowId"
              :loading="loading && !items.length"
              :loading-label="t('common.loading')"
              :empty-label="t('skills.emptyTable')"
            >
              <template #cell-activate="{ original }">
                <div class="flex items-center">
                  <Switch
                    :model-value="original.activate"
                    :disabled="
                      togglingFolder === skillDiskFolder(original) || !hasOsAuth
                    "
                    :aria-label="
                      original.activate
                        ? t('skills.activateSwitch.disableAria', {
                            name: original.name,
                          })
                        : t('skills.activateSwitch.enableAria', {
                            name: original.name,
                          })
                    "
                    @update:model-value="
                      (v) => onToggleActivate(skillDiskFolder(original), v)
                    "
                  />
                </div>
              </template>
              <template #cell-actions="{ original }">
                <div class="flex justify-end">
                  <DropdownMenu
                    :modal="false"
                    :open="openActionsForName === skillDiskFolder(original)"
                    @update:open="onActionsMenuOpenChange"
                  >
                    <DropdownMenuTrigger as-child>
                      <Button
                        variant="ghost"
                        size="icon"
                        class="h-8 w-8 shrink-0 text-muted-foreground hover:bg-accent dark:hover:bg-white/10"
                        :aria-label="t('skills.actionsAria')"
                        @pointerenter="showActionsMenu(skillDiskFolder(original))"
                        @pointerleave="scheduleActionsMenuClose()"
                      >
                        <MoreVertical class="size-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent
                      align="end"
                      class="w-40"
                      @pointerenter="
                        onActionsContentPointerEnter(skillDiskFolder(original))
                      "
                      @pointerleave="scheduleActionsMenuClose()"
                    >
                      <DropdownMenuItem
                        class="text-xs font-semibold uppercase tracking-wide"
                        :disabled="
                          replacingName === skillDiskFolder(original) || uploading
                        "
                        @select="
                          () => {
                            triggerReplace(skillDiskFolder(original))
                          }
                        "
                      >
                        {{
                          replacingName === skillDiskFolder(original)
                            ? t('skills.updating')
                            : t('skills.update')
                        }}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        variant="destructive"
                        class="text-xs font-semibold uppercase tracking-wide"
                        :disabled="deletingName === skillDiskFolder(original)"
                        @select="
                          () => {
                            requestDelete(skillDiskFolder(original))
                          }
                        "
                      >
                        {{ t("common.delete") }}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </template>
            </DataTable>
          </div>
        </div>
      </div>
    </div>

    <AlertDialog v-model:open="deleteConfirmOpen">
      <AlertDialogContent class="sm:max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle>{{ t("skills.deleteTitle") }}</AlertDialogTitle>
          <AlertDialogDescription>
            {{ t("skills.deleteDescription", { name: pendingDeleteName }) }}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel @click="pendingDeleteName = null">
            {{ t("common.cancel") }}
          </AlertDialogCancel>
          <Button
            type="button"
            variant="destructive"
            @click="void confirmDelete()"
          >
            {{ t("common.delete") }}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </AppPageScaffold>
</template>
