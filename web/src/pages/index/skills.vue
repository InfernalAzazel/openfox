<script setup lang="ts">
import type { DropdownMenuItem, TableColumn } from "@nuxt/ui"
import { computed, h, nextTick, onMounted, ref, resolveComponent, watch } from "vue"
import { useI18n } from "vue-i18n"
import {
  deleteOpenFoxSkillAPI,
  listOpenFoxSkillsAPI,
  patchOpenFoxSkillActivateAPI,
  replaceOpenFoxSkillAPI,
  uploadOpenFoxSkillAPI,
  type OpenFoxSkillInfo,
} from "@/api/os"
import { getAgentOsBaseUrl } from "@/composables/request"
import { useAppState } from "@/composables/store"

const { t, locale } = useI18n()
const app = useAppState()

const USwitchComp = resolveComponent("USwitch")
const UDropdownMenuComp = resolveComponent("UDropdownMenu")
const UButtonComp = resolveComponent("UButton")

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
const SKILLS_PAGE_SIZE = 5
const skillsPage = ref(1)

function skillDiskFolder(s: OpenFoxSkillInfo): string {
  const normalized = s.path.replace(/\\/g, "/")
  const parts = normalized.split("/").filter(Boolean)
  return parts[parts.length - 1] || s.name
}

function skillRowId(row: OpenFoxSkillInfo) {
  return row.path
}

const pagedItems = computed(() => {
  const start = (skillsPage.value - 1) * SKILLS_PAGE_SIZE
  return items.value.slice(start, start + SKILLS_PAGE_SIZE)
})

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
  if (!silent) loading.value = true
  pageError.value = null
  try {
    const r = await listOpenFoxSkillsAPI(base, token)
    if (!r.ok) {
      pageError.value = t("skills.loadFailed", { status: r.status, message: r.message })
      return
    }
    items.value = r.data
    await nextTick()
  } finally {
    if (!silent) loading.value = false
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
  if (row && row.activate === activate) return
  togglingFolder.value = diskFolder
  pageError.value = null
  pageSuccess.value = null
  try {
    const r = await patchOpenFoxSkillActivateAPI(base, token, diskFolder, activate)
    if (!r.ok) {
      pageError.value = t("skills.toggleFailed", { status: r.status, message: r.message })
      return
    }
    pageSuccess.value = t("skills.activateUpdated", { name: r.skill.name })
    await loadList({ silent: true })
  } finally {
    togglingFolder.value = null
  }
}

const tableColumns = computed<TableColumn<OpenFoxSkillInfo>[]>(() => {
  void locale.value
  return [
    {
      id: "activate",
      header: t("skills.colActivate"),
      meta: { class: { th: "w-16 shrink-0", td: "w-16 shrink-0" } },
      cell: ({ row }) =>
        h(USwitchComp as any, {
          "modelValue": row.original.activate,
          "size": "sm",
          "disabled": togglingFolder.value === skillDiskFolder(row.original) || !hasOsAuth.value,
          "onUpdate:modelValue": (v: boolean) => onToggleActivate(skillDiskFolder(row.original), v),
        }),
    },
    {
      accessorKey: "name",
      header: t("skills.colName"),
      meta: {
        class: {
          th: "w-[10rem] min-w-0 shrink-0 font-mono",
          td: "min-w-0 max-w-0 overflow-hidden",
        },
      },
      cell: ({ row }) => {
        const name = row.original.name
        return h(
          "span",
          {
            class:
              "block w-full min-w-0 truncate font-mono text-sm font-medium text-foreground",
            title: name,
          },
          name,
        )
      },
    },
    {
      accessorKey: "description",
      header: t("skills.colDescription"),
      meta: {
        class: {
          th: "min-w-0 w-[38%]",
          td: "min-w-0 max-w-0 overflow-hidden",
        },
      },
      cell: ({ row }) => {
        const text = String(row.original.description ?? "")
        return h(
          "span",
          {
            class:
              "block w-full min-w-0 truncate text-sm text-muted-foreground",
            title: text,
          },
          text,
        )
      },
    },
    {
      accessorKey: "path",
      header: t("skills.colPath"),
      meta: {
        class: {
          th: "min-w-0 w-[34%] font-mono",
          td: "min-w-0 max-w-0 overflow-hidden",
        },
      },
      cell: ({ row }) =>
        h(
          "span",
          {
            class:
              "block w-full min-w-0 truncate font-mono text-sm text-muted-foreground",
            title: row.original.path,
          },
          row.original.path,
        ),
    },
    {
      accessorKey: "license",
      header: t("skills.colLicense"),
      meta: {
        class: {
          th: "w-24 shrink-0",
          td: "w-24 min-w-0 max-w-0 shrink-0 overflow-hidden",
        },
      },
      cell: ({ row }) => {
        const v = row.original.license
        const s = typeof v === "string" ? v.trim() : ""
        const shown = s || t("skills.emptyCell")
        return h(
          "span",
          {
            class:
              "block w-full min-w-0 truncate text-sm tabular-nums text-muted-foreground",
            title: s ? s : undefined,
          },
          shown,
        )
      },
    },
    {
      id: "actions",
      header: () => h("span", { class: "block w-full text-right" }, t("skills.colActions")),
      meta: { class: { th: "w-14 shrink-0 pr-2 text-right", td: "w-14 shrink-0 pr-2 text-right" } },
      cell: ({ row }) => {
        const folder = skillDiskFolder(row.original)
        const dropdownItems: DropdownMenuItem[][] = [[
          {
            label: replacingName.value === folder ? t("skills.updating") : t("skills.update"),
            disabled: replacingName.value === folder || uploading.value,
            onSelect: () => triggerReplace(folder),
          },
          {
            label: t("common.delete"),
            color: "error" as const,
            disabled: deletingName.value === folder,
            onSelect: () => requestDelete(folder),
          },
        ]]
        return h("div", { class: "flex justify-end" }, [
          h(UDropdownMenuComp as any, {
            items: dropdownItems,
            modal: false,
            content: { align: "end" },
          }, {
            default: () => h(UButtonComp as any, {
              variant: "ghost",
              color: "neutral",
              size: "sm",
              icon: "i-lucide-ellipsis-vertical",
              square: true,
            }),
          }),
        ])
      },
    },
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
      pageError.value = r.status === 409
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
      pageError.value = t("skills.updateFailed", { status: r.status, message: r.message })
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
      pageError.value = t("skills.deleteFailed", { status: r.status, message: r.message })
      return
    }
    pageSuccess.value = t("skills.deleted", { name })
    await loadList()
  } finally {
    deletingName.value = null
  }
}

onMounted(() => {
  if (hasOsAuth.value) {
    void loadList()
  } else {
    pageError.value = t("skills.needLoginOs")
  }
})

/** 与 sessions 页 UTable 一致（紧凑表头 + 斑马线 + 行高） */
const skillsTableUi = {
  root: "overflow-x-auto",
  base: "min-w-full table-fixed",
  thead: "bg-elevated/40",
  th: "border-b border-default py-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground",
  tbody: "divide-y divide-default",
  tr: "odd:bg-default even:bg-elevated/30 hover:bg-elevated/45 dark:even:bg-white/[0.06]",
  td: "py-2 px-3 text-sm align-middle",
  separator: "hidden",
  empty: "py-8 text-sm text-muted-foreground",
  loading: "py-8 text-sm",
}

watch(
  () => items.value.length,
  (len) => {
    const max = Math.max(1, Math.ceil(len / SKILLS_PAGE_SIZE))
    if (skillsPage.value > max) skillsPage.value = max
  },
)
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col overflow-auto bg-background">
    <div class="w-full space-y-4 p-4 text-foreground md:p-6">
      <UAlert
        v-if="pageError"
        color="error"
        variant="subtle"
        class="shrink-0"
        :description="pageError"
      />
      <UAlert
        v-else-if="pageSuccess"
        color="success"
        variant="subtle"
        class="shrink-0"
        :description="pageSuccess"
      />
      <UAlert
        v-else-if="!hasOsAuth"
        color="warning"
        variant="subtle"
        class="shrink-0 rounded-lg border-dashed"
        :description="t('skills.manageHint')"
      />

      <div class="min-w-0 flex-1">
        <div class="overflow-hidden rounded-lg border border-default bg-default shadow-sm">
          <div
            class="flex min-h-12 flex-nowrap items-center justify-between gap-3 overflow-x-auto border-b border-default px-3 py-3 sm:min-h-14 sm:px-4 sm:py-3.5"
          >
            <span class="shrink-0 text-xs text-muted-foreground">
              {{
                loading && !items.length
                  ? t("common.loading")
                  : t("common.itemsInTable", { count: items.length })
              }}
            </span>
            <div class="flex shrink-0 items-center gap-2 sm:gap-3">
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
              <UTooltip :text="t('skills.uploadZipHint')">
                <UButton
                  variant="solid"
                  color="primary"
                  size="sm"
                  icon="i-lucide-plus"
                  :disabled="!hasOsAuth || uploading"
                  :loading="uploading"
                  @click="triggerUpload"
                >
                  {{ uploading ? t("skills.uploading") : t("skills.createSkill") }}
                </UButton>
              </UTooltip>
              <UButton
                variant="outline"
                color="neutral"
                size="sm"
                square
                icon="i-lucide-refresh-cw"
                :aria-label="t('skills.refreshList')"
                :title="t('skills.refreshList')"
                :disabled="!hasOsAuth || loading"
                :loading="loading"
                @click="void loadList()"
              />
            </div>
          </div>

          <UTable
            :data="pagedItems"
            :columns="tableColumns"
            :loading="loading && !items.length"
            :get-row-id="skillRowId"
            :empty="t('skills.emptyTable')"
            sticky="header"
            class="w-full min-w-0"
            :ui="skillsTableUi"
          >
            <template #loading>
              <span class="text-muted-foreground">{{ t("common.loading") }}</span>
            </template>
          </UTable>
          <div class="flex justify-end border-t border-default px-3 py-2 sm:px-4">
            <UPagination
              v-model:page="skillsPage"
              :items-per-page="SKILLS_PAGE_SIZE"
              :total="items.length"
              size="sm"
            />
          </div>
        </div>
      </div>

      <UModal
        v-model:open="deleteConfirmOpen"
        :title="t('skills.deleteTitle')"
        :description="t('skills.deleteDescription', { name: pendingDeleteName })"
        :close="false"
      >
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              type="button"
              @click="deleteConfirmOpen = false; pendingDeleteName = null"
            >
              {{ t("common.cancel") }}
            </UButton>
            <UButton
              color="error"
              size="sm"
              type="button"
              @click="void confirmDelete()"
            >
              {{ t("common.delete") }}
            </UButton>
          </div>
        </template>
      </UModal>
    </div>
  </div>
</template>
