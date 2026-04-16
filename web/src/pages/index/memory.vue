<script setup lang="ts">
import type { TableColumn, TableRow } from "@nuxt/ui"
import type { FormSubmitEvent } from "@nuxt/ui"
import { h, computed, onMounted, reactive, ref, resolveComponent, watch } from "vue"
import { useI18n } from "vue-i18n"
import { z } from "zod"
import {
  getUserMemoryStatsAPI,
  listMemoriesAPI,
  createMemoryAPI,
  updateMemoryAPI,
  deleteMemoryAPI,
  deleteMemoriesBatchAPI,
} from "@/api/memory"
import { getAgentsAPI } from "@/api/os"
import type { UserStats, UserMemory } from "@/api/memory"
import { getAgentOsBaseUrl } from "@/composables/request"
import { useAppState } from "@/composables/store"
import type { AgentDetails } from "@/types/os"

const { t, locale } = useI18n()
const app = useAppState()

const UCheckbox = resolveComponent("UCheckbox")

type ViewLevel = "users" | "memories"

const viewLevel = ref<ViewLevel>("users")
const selectedUserId = ref("")
const agents = ref<AgentDetails[]>([])
const selectedAgentId = ref("")

const userStats = ref<UserStats[]>([])
const loadingUsers = ref(false)
const usersTotalCount = ref(0)
const MEMORY_USERS_PAGE_SIZE = 10
const usersPage = ref(1)

const memories = ref<UserMemory[]>([])
const loadingMemories = ref(false)
const memoriesTotalCount = ref(0)
const MEMORY_PAGE_SIZE = 10
const memoriesPage = ref(1)

const selectedMemory = ref<UserMemory | null>(null)
const editContent = ref("")
const editTopics = ref<string[]>([])
const newTopicInput = ref("")
const saving = ref(false)
const deleting = ref(false)
const deleteConfirmOpen = ref(false)

const sortDesc = ref(true)

const rowSelection = ref<Record<string, boolean>>({})
const batchDeleting = ref(false)
const batchDeleteConfirmOpen = ref(false)

const selectedIds = computed(() =>
  Object.keys(rowSelection.value).filter((k) => rowSelection.value[k]),
)
const selectedCount = computed(() => selectedIds.value.length)

const pagedUserStats = computed(() => {
  const start = (usersPage.value - 1) * MEMORY_USERS_PAGE_SIZE
  return userStats.value.slice(start, start + MEMORY_USERS_PAGE_SIZE)
})

const pagedMemories = computed(() => {
  const start = (memoriesPage.value - 1) * MEMORY_PAGE_SIZE
  return memories.value.slice(start, start + MEMORY_PAGE_SIZE)
})

const errorMessage = ref<string | null>(null)

const hasOsAuth = computed(() => {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim()
  return !!(base && token)
})

function authHeaders() {
  const base = getAgentOsBaseUrl()
  const token = app.value.access_token?.trim()
  return { base, token }
}

const selectedAgent = computed(() =>
  agents.value.find((a) => a.id === selectedAgentId.value),
)

const memoryTableName = "agno_memories"

const memoryHeaderMeta = computed(() => {
  const fullId = selectedAgent.value?.db_id?.trim() || ""
  return {
    fullId: fullId || "—",
    table: memoryTableName,
  }
})

const memoryDbIdEllipsis = computed(() => {
  const id = memoryHeaderMeta.value.fullId
  if (id === "—") return id
  const max = 28
  return id.length <= max ? id : `${id.slice(0, max)}...`
})

async function refreshAgents() {
  const { base, token } = authHeaders()
  if (!base || !token) return
  try {
    agents.value = await getAgentsAPI(base, token)
    if (!agents.value.length) {
      selectedAgentId.value = ""
      return
    }
    if (!selectedAgentId.value || !agents.value.some((a) => a.id === selectedAgentId.value)) {
      selectedAgentId.value = agents.value[0]!.id
    }
  } catch {
    agents.value = []
    selectedAgentId.value = ""
  }
}

function formatDateTime(ts: string | null | undefined): string {
  if (!ts) return "—"
  try {
    const d = new Date(ts)
    const loc = locale.value === "zh-CN" ? "zh-CN" : "en-GB"
    return new Intl.DateTimeFormat(loc, {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).format(d)
  } catch {
    return "—"
  }
}

// --- Level 1: User Stats ---

async function refreshUserStats() {
  const { base, token } = authHeaders()
  if (!base || !token) return
  loadingUsers.value = true
  errorMessage.value = null
  try {
    const res = await getUserMemoryStatsAPI(base, token, { limit: 100 })
    if (!res.ok) {
      errorMessage.value = t("memory.loadFailed", { message: res.message })
      userStats.value = []
      return
    }
    userStats.value = res.data.data
    usersTotalCount.value = res.data.meta.total_count
  } finally {
    loadingUsers.value = false
  }
}

function selectUser(_e: Event, row: TableRow<UserStats>) {
  selectedUserId.value = row.original.user_id
  selectedMemory.value = null
  viewLevel.value = "memories"
  memoriesPage.value = 1
  void refreshMemories()
}

function clearSelection() {
  rowSelection.value = {}
  batchDeleteConfirmOpen.value = false
}

function openBatchDeleteConfirm() {
  if (!selectedIds.value.length || batchDeleting.value) return
  batchDeleteConfirmOpen.value = true
}

async function confirmBatchDelete() {
  if (!selectedIds.value.length || batchDeleting.value) return
  const { base, token } = authHeaders()
  if (!base || !token) return
  batchDeleting.value = true
  errorMessage.value = null
  try {
    const res = await deleteMemoriesBatchAPI(
      base,
      token,
      [...selectedIds.value],
      selectedUserId.value || undefined,
    )
    if (!res.ok) {
      errorMessage.value = t("memory.deleteFailed", { message: res.message })
      return
    }
    rowSelection.value = {}
    batchDeleteConfirmOpen.value = false
    await refreshMemories()
  } finally {
    batchDeleting.value = false
  }
}

function backToUsers() {
  viewLevel.value = "users"
  selectedUserId.value = ""
  selectedMemory.value = null
  rowSelection.value = {}
  memoriesPage.value = 1
  void refreshUserStats()
}

const userColumns = computed<TableColumn<UserStats>[]>(() => [
  {
    accessorKey: "user_id",
    header: t("memory.colUserId"),
    meta: {
      class: {
        th: "min-w-0 w-[50%]",
        td: "max-w-0 min-w-0",
      },
    },
    cell: ({ row }) =>
      h(
        "span",
        {
          class: "block min-w-0 truncate text-sm font-normal text-foreground",
          title: row.original.user_id,
        },
        row.original.user_id,
      ),
  },
  {
    accessorKey: "total_memories",
    header: t("memory.colMemories"),
    meta: {
      class: {
        th: "text-center w-[20%]",
        td: "text-center text-sm tabular-nums text-muted-foreground",
      },
    },
  },
  {
    id: "updated_at",
    accessorFn: (row) => row.last_memory_updated_at ?? "",
    header: t("memory.colUpdatedAt"),
    cell: ({ row }) =>
      formatDateTime(row.original.last_memory_updated_at),
    meta: {
      class: {
        th: "text-right w-[30%]",
        td: "text-right text-sm whitespace-nowrap tabular-nums text-muted-foreground",
      },
    },
  },
])

// --- Level 2: Memory List ---

async function refreshMemories() {
  const { base, token } = authHeaders()
  if (!base || !token || !selectedUserId.value) return
  loadingMemories.value = true
  errorMessage.value = null
  try {
    const res = await listMemoriesAPI(base, token, {
      user_id: selectedUserId.value,
      limit: 100,
      sort_by: "updated_at",
      sort_order: sortDesc.value ? "desc" : "asc",
    })
    if (!res.ok) {
      errorMessage.value = t("memory.loadFailed", { message: res.message })
      memories.value = []
      return
    }
    memories.value = res.data.data
    memoriesTotalCount.value = res.data.meta.total_count
    const alive = new Set(res.data.data.map((m) => m.memory_id))
    const next = { ...rowSelection.value }
    for (const k of Object.keys(next)) {
      if (!alive.has(k)) delete next[k]
    }
    rowSelection.value = next
  } finally {
    loadingMemories.value = false
  }
}

function selectMemoryRow(_e: Event, row: TableRow<UserMemory>) {
  const memory = row.original
  selectedMemory.value = { ...memory }
  editContent.value = memory.memory
  editTopics.value = [...(memory.topics ?? [])]
  newTopicInput.value = ""
}

const memoryColumns = computed<TableColumn<UserMemory>[]>(() => [
  {
    id: "select",
    meta: {
      class: {
        th: "w-10",
        td: "w-10",
      },
    },
    header: ({ table }) =>
      h(UCheckbox, {
        "modelValue": table.getIsSomePageRowsSelected()
          ? "indeterminate"
          : table.getIsAllPageRowsSelected(),
        "onUpdate:modelValue": (value: boolean | "indeterminate") =>
          table.toggleAllPageRowsSelected(!!value),
        "aria-label": t("memory.selectAll"),
      }),
    cell: ({ row }) =>
      h(UCheckbox, {
        "modelValue": row.getIsSelected(),
        "onUpdate:modelValue": (value: boolean | "indeterminate") =>
          row.toggleSelected(!!value),
        "aria-label": t("memory.selectRow"),
      }),
    enableSorting: false,
    enableHiding: false,
  },
  {
    accessorKey: "memory",
    header: t("memory.colContent"),
    meta: {
      class: {
        th: "min-w-0 w-[50%]",
        td: "max-w-0 min-w-0",
      },
    },
    cell: ({ row }) =>
      h(
        "span",
        {
          class: "block min-w-0 truncate text-sm font-normal text-foreground",
          title: row.original.memory,
        },
        row.original.memory,
      ),
  },
  {
    id: "topics",
    accessorFn: (row) => (row.topics ?? []).join(", "),
    header: t("memory.colTopics"),
    meta: {
      class: {
        th: "w-[25%]",
        td: "max-w-0 min-w-0",
      },
    },
    cell: ({ row }) => {
      const topics = row.original.topics ?? []
      if (!topics.length)
        return h("span", { class: "text-muted-foreground" }, "—")
      const fullText = topics.join(", ")
      return h(
        "div",
        { class: "flex min-w-0 gap-1 overflow-hidden", title: fullText },
        [
          ...topics.slice(0, 3).map((t) =>
            h(
              "span",
              {
                class:
                  "inline-flex shrink-0 items-center truncate rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground",
              },
              t,
            ),
          ),
          ...(topics.length > 3
            ? [
                h(
                  "span",
                  {
                    class: "shrink-0 text-xs text-muted-foreground",
                  },
                  `+${topics.length - 3}`,
                ),
              ]
            : []),
        ],
      )
    },
  },
  {
    id: "updated_at",
    accessorFn: (row) => row.updated_at ?? "",
    header: () =>
      h("div", { class: "flex justify-end" }, [
        h(resolveComponent("UButton"), {
          color: "neutral",
          variant: "ghost",
          size: "sm",
          label: t("memory.colUpdatedAt"),
          icon: sortDesc.value
            ? "i-lucide-arrow-down-wide-narrow"
            : "i-lucide-arrow-up-narrow-wide",
          class: "-mx-2.5 text-xs font-semibold uppercase tracking-wider",
          onClick: () => {
            sortDesc.value = !sortDesc.value
          },
        }),
      ]),
    cell: ({ row }) => formatDateTime(row.original.updated_at),
    meta: {
      class: {
        th: "text-right w-[25%]",
        td: "text-right text-sm whitespace-nowrap tabular-nums text-muted-foreground",
      },
    },
  },
])

// --- Create Memory Dialog ---

const USER_ID_RE = /^[A-Za-z0-9._@+:\-]+$/

const createSchema = z.object({
  user_id: z
    .string()
    .min(1, t("memory.userIdRequired"))
    .regex(USER_ID_RE, t("memory.userIdInvalid")),
  memory: z.string().min(1, t("memory.contentRequired")),
  topicInput: z.string().optional(),
})

type CreateSchema = z.output<typeof createSchema>

const createDialogOpen = ref(false)
const createFormState = reactive<CreateSchema>({
  user_id: "",
  memory: "",
  topicInput: "",
})
const createTopics = ref<string[]>([])
const creating = ref(false)

function openCreateDialog() {
  createFormState.user_id = selectedUserId.value || ""
  createFormState.memory = ""
  createFormState.topicInput = ""
  createTopics.value = []
  createDialogOpen.value = true
}

function addCreateTopic() {
  const val = (createFormState.topicInput ?? "").trim()
  if (val && !createTopics.value.includes(val)) {
    createTopics.value.push(val)
  }
  createFormState.topicInput = ""
}

function removeCreateTopic(topic: string) {
  createTopics.value = createTopics.value.filter((t) => t !== topic)
}

function handleCreateTopicKeydown(e: KeyboardEvent) {
  if (e.key === "Enter") {
    e.preventDefault()
    addCreateTopic()
  }
}

async function onCreateSubmit(event: FormSubmitEvent<CreateSchema>) {
  const { base, token } = authHeaders()
  if (!base || !token) return

  creating.value = true
  errorMessage.value = null
  try {
    const res = await createMemoryAPI(base, token, {
      memory: event.data.memory.trim(),
      user_id: event.data.user_id?.trim() || undefined,
      topics: createTopics.value.length ? createTopics.value : undefined,
    })
    if (!res.ok) {
      errorMessage.value = t("memory.createFailed", { message: res.message })
      return
    }
    createDialogOpen.value = false
    const createdUserId = event.data.user_id?.trim() || ""
    if (viewLevel.value === "memories" && selectedUserId.value === createdUserId) {
      await refreshMemories()
    } else if (viewLevel.value === "users") {
      await refreshUserStats()
    }
  } finally {
    creating.value = false
  }
}

// --- Level 3: Detail / Edit ---

function addTopic() {
  const val = newTopicInput.value.trim()
  if (val && !editTopics.value.includes(val)) {
    editTopics.value.push(val)
  }
  newTopicInput.value = ""
}

function removeTopic(topic: string) {
  editTopics.value = editTopics.value.filter((t) => t !== topic)
}

function handleTopicKeydown(e: KeyboardEvent) {
  if (e.key === "Enter") {
    e.preventDefault()
    addTopic()
  }
}

async function saveMemory() {
  const { base, token } = authHeaders()
  if (!base || !token || !selectedMemory.value) return
  if (!editContent.value.trim()) return

  saving.value = true
  errorMessage.value = null
  try {
    const res = await updateMemoryAPI(
      base,
      token,
      selectedMemory.value.memory_id,
      {
        memory: editContent.value.trim(),
        user_id: selectedMemory.value.user_id || undefined,
        topics: editTopics.value.length ? editTopics.value : undefined,
      },
    )
    if (!res.ok) {
      errorMessage.value = t("memory.saveFailed", { message: res.message })
      return
    }
    selectedMemory.value = null
    await refreshMemories()
  } finally {
    saving.value = false
  }
}

async function confirmDeleteMemory() {
  const { base, token } = authHeaders()
  if (!base || !token || !selectedMemory.value) return

  deleting.value = true
  errorMessage.value = null
  try {
    const res = await deleteMemoryAPI(
      base,
      token,
      selectedMemory.value.memory_id,
      selectedMemory.value.user_id ?? undefined,
    )
    if (!res.ok) {
      errorMessage.value = t("memory.deleteFailed", { message: res.message })
      return
    }
    selectedMemory.value = null
    deleteConfirmOpen.value = false
    await refreshMemories()
  } finally {
    deleting.value = false
  }
}

function cancelDetail() {
  selectedMemory.value = null
}

const memoryTableMeta = computed(() => ({
  class: {
    tr: (row: { original: UserMemory }) =>
      [
        "cursor-pointer transition-colors",
        selectedMemory.value && row.original?.memory_id === selectedMemory.value.memory_id
          ? "[&_td:not(:first-child)]:!text-primary [&_td:not(:first-child)_span]:!text-primary"
          : "",
      ].filter(Boolean).join(" "),
  },
}))

const tableUi = {
  root: "overflow-x-auto",
  base: "min-w-full table-fixed",
  thead: "bg-elevated/40",
  th: "border-b border-default py-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground",
  tbody: "divide-y divide-default",
  tr: "odd:bg-default even:bg-elevated/30 hover:bg-elevated/45 cursor-pointer dark:even:bg-white/[0.06]",
  td: "py-3 px-3 text-sm align-middle",
  separator: "hidden",
  empty: "py-8 text-sm text-muted-foreground",
  loading: "py-8 text-sm",
}

onMounted(() => {
  if (hasOsAuth.value) {
    void refreshAgents()
    void refreshUserStats()
  }
})

watch(
  () => app.value.access_token,
  () => {
    if (hasOsAuth.value) {
      void refreshAgents()
      viewLevel.value = "users"
      selectedUserId.value = ""
      selectedMemory.value = null
      void refreshUserStats()
    }
  },
)

watch(selectedCount, (n) => {
  if (n === 0) batchDeleteConfirmOpen.value = false
})

watch(userStats, (rows) => {
  const max = Math.max(1, Math.ceil(rows.length / MEMORY_USERS_PAGE_SIZE))
  if (usersPage.value > max) usersPage.value = max
})

watch(memories, (rows) => {
  const max = Math.max(1, Math.ceil(rows.length / MEMORY_PAGE_SIZE))
  if (memoriesPage.value > max) memoriesPage.value = max
})

watch(sortDesc, () => {
  if (viewLevel.value === "memories") {
    void refreshMemories()
  }
})
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col overflow-auto bg-background">
    <div class="w-full space-y-4 p-4 text-foreground md:p-6">
      <div class="flex w-full flex-wrap items-end gap-x-4 gap-y-3">
        <div
          class="inline-grid min-w-0 max-w-full grid-cols-[auto_auto] grid-rows-[auto_auto] gap-x-3 gap-y-0.5 sm:max-w-[min(100%,36rem)] sm:gap-x-4"
        >
          <span class="col-start-1 row-start-1 text-xs leading-none text-muted-foreground">
            {{ t("common.metaDatabase") }}
          </span>
          <span class="col-start-2 row-start-1 text-xs leading-none text-muted-foreground">
            {{ t("common.metaTable") }}
          </span>
          <span
            class="col-start-1 row-start-2 min-w-0 max-w-[min(100%,20rem)] font-mono text-sm leading-snug font-medium whitespace-nowrap sm:max-w-[24rem]"
            :title="memoryHeaderMeta.fullId !== '—' ? memoryHeaderMeta.fullId : undefined"
          >
            {{ memoryDbIdEllipsis }}
          </span>
          <span class="col-start-2 row-start-2 font-mono text-sm leading-snug font-medium whitespace-nowrap">
            {{ memoryHeaderMeta.table }}
          </span>
        </div>
      </div>

      <UAlert
        v-if="errorMessage && hasOsAuth"
        color="error"
        variant="subtle"
        class="shrink-0"
        :description="errorMessage"
      />

      <UAlert
        v-if="!hasOsAuth"
        color="warning"
        variant="subtle"
        class="rounded-lg border-dashed"
        :description="t('memory.needLogin')"
      />

      <!-- ========== Level 1: User Stats ========== -->
      <template v-else-if="viewLevel === 'users'">
        <div
          class="overflow-hidden rounded-lg border border-default bg-default shadow-sm"
        >
          <div
            class="flex min-h-12 flex-nowrap items-center justify-between gap-3 border-b border-default px-3 py-3 sm:min-h-14 sm:px-4 sm:py-3.5"
          >
            <span class="shrink-0 text-xs text-muted-foreground">
              {{
                loadingUsers
                  ? t("common.loading")
                  : t("common.itemsInTable", { count: userStats.length })
              }}
            </span>
            <div class="flex items-center gap-3">
              <UButton
                color="primary"
                variant="solid"
                size="sm"
                icon="i-lucide-plus"
                :label="t('memory.createMemory')"
                @click="openCreateDialog"
              />
              <UButton
                color="neutral"
                variant="outline"
                size="sm"
                square
                icon="i-lucide-refresh-cw"
                :aria-label="t('common.refresh')"
                :title="t('common.refresh')"
                :disabled="loadingUsers"
                :loading="loadingUsers"
                class="shrink-0"
                @click="void refreshUserStats()"
              />
            </div>
          </div>

          <UTable
            :data="pagedUserStats"
            :columns="userColumns"
            :loading="loadingUsers"
            :empty="t('memory.emptyUsers')"
            sticky="header"
            class="w-full min-w-0"
            :ui="tableUi"
            @select="selectUser"
          >
            <template #loading>
              <span class="text-muted-foreground">{{
                t("common.loading")
              }}</span>
            </template>
          </UTable>
          <div class="flex justify-end border-t border-default px-3 py-2 sm:px-4">
            <UPagination
              v-model:page="usersPage"
              :items-per-page="MEMORY_USERS_PAGE_SIZE"
              :total="userStats.length"
              size="sm"
            />
          </div>
        </div>
      </template>

      <!-- ========== Level 2 & 3: Memory List + Detail Panel ========== -->
      <template v-else-if="viewLevel === 'memories'">
        <div class="flex gap-4" :class="selectedMemory ? 'flex-col lg:flex-row' : ''">
          <!-- Left: Memory List -->
          <div
            class="overflow-hidden rounded-lg border border-default bg-default shadow-sm"
            :class="selectedMemory ? 'lg:w-1/2' : 'w-full'"
          >
            <div
              class="flex min-h-12 flex-nowrap items-center justify-between gap-3 border-b border-default px-3 py-3 sm:min-h-14 sm:px-4 sm:py-3.5"
            >
              <div class="flex items-center gap-3">
                <UButton
                  color="neutral"
                  variant="ghost"
                  size="sm"
                  icon="i-lucide-chevron-left"
                  @click="backToUsers"
                />
                <span class="shrink-0 text-xs text-muted-foreground">
                  {{ t("common.itemsInTable", { count: memories.length }) }}
                </span>
              </div>
              <div class="flex shrink-0 items-center justify-end gap-2 sm:gap-3">
                <template v-if="selectedCount > 0">
                  <span
                    class="shrink-0 text-xs tabular-nums text-muted-foreground"
                    role="status"
                    aria-live="polite"
                  >
                    {{ t("memory.selectedCount", { count: selectedCount }) }}
                  </span>
                  <UButton
                    variant="outline"
                    color="neutral"
                    size="sm"
                    class="shrink-0"
                    :disabled="batchDeleting"
                    @click="clearSelection"
                  >
                    {{ t("common.cancel") }}
                  </UButton>
                  <UButton
                    color="error"
                    variant="solid"
                    size="sm"
                    class="shrink-0"
                    :disabled="batchDeleting"
                    @click="openBatchDeleteConfirm"
                  >
                    {{ t("common.delete") }}
                  </UButton>
                </template>
                <template v-else>
                  <UButton
                    color="primary"
                    variant="solid"
                    size="sm"
                    icon="i-lucide-plus"
                    :label="t('memory.createMemory')"
                    @click="openCreateDialog"
                  />
                  <UButton
                    color="neutral"
                    variant="outline"
                    size="sm"
                    square
                    icon="i-lucide-refresh-cw"
                    :aria-label="t('common.refresh')"
                    :title="t('common.refresh')"
                    :disabled="loadingMemories"
                    :loading="loadingMemories"
                    class="shrink-0"
                    @click="void refreshMemories()"
                  />
                </template>
              </div>
            </div>

            <!-- Breadcrumb: Database / Table / User ID -->
            <div
              class="flex flex-wrap items-center gap-x-2 gap-y-0.5 border-b border-default bg-elevated/30 px-4 py-2 text-xs text-muted-foreground"
            >
              <span class="font-medium">User ID</span>
              <span class="font-mono">{{ selectedUserId }}</span>
            </div>

            <UTable
              v-model:row-selection="rowSelection"
              :data="pagedMemories"
              :columns="memoryColumns"
              :loading="loadingMemories"
              :get-row-id="(row: UserMemory) => row.memory_id"
              :empty="t('memory.emptyMemories')"
              sticky="header"
              class="w-full min-w-0"
              :ui="tableUi"
              :meta="memoryTableMeta"
              @select="selectMemoryRow"
            >
              <template #loading>
                <span class="text-muted-foreground">{{
                  t("common.loading")
                }}</span>
              </template>
            </UTable>
            <div class="flex justify-end border-t border-default px-3 py-2 sm:px-4">
              <UPagination
                v-model:page="memoriesPage"
                :items-per-page="MEMORY_PAGE_SIZE"
                :total="memories.length"
                size="sm"
              />
            </div>
          </div>

          <!-- Right: Detail Panel (Level 3) -->
          <div
            v-if="selectedMemory"
            class="flex flex-col rounded-lg border border-default bg-default shadow-sm lg:w-1/2"
          >
            <!-- Detail Header -->
            <div
              class="flex items-start justify-between gap-3 border-b border-default px-4 py-4"
            >
              <p class="text-sm leading-relaxed font-medium text-foreground">
                {{ selectedMemory.memory }}
              </p>
              <UButton
                color="neutral"
                variant="ghost"
                size="sm"
                square
                icon="i-lucide-x"
                @click="cancelDetail"
              />
            </div>

            <!-- Detail Body -->
            <div class="flex-1 space-y-5 overflow-auto p-4">
              <!-- Content -->
              <div class="space-y-1.5">
                <label class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  {{ t("memory.content") }}
                </label>
                <UTextarea
                  v-model="editContent"
                  :placeholder="t('memory.contentPlaceholder')"
                  :rows="4"
                  autoresize
                  class="w-full"
                />
              </div>

              <!-- Topics -->
              <div class="space-y-1.5">
                <label class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  {{ t("memory.topicsOptional") }}
                </label>
                <div class="flex items-center gap-2">
                  <UInput
                    v-model="newTopicInput"
                    :placeholder="t('memory.topicsPlaceholder')"
                    class="flex-1"
                    size="sm"
                    @keydown="handleTopicKeydown"
                  />
                  <UButton
                    color="neutral"
                    variant="outline"
                    size="sm"
                    square
                    icon="i-lucide-plus"
                    @click="addTopic"
                  />
                </div>
                <div v-if="editTopics.length" class="flex flex-wrap gap-1.5 pt-1">
                  <span
                    v-for="topic in editTopics"
                    :key="topic"
                    class="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-foreground"
                  >
                    {{ topic }}
                    <button
                      type="button"
                      class="ml-0.5 rounded-full p-0.5 text-muted-foreground hover:bg-foreground/10 hover:text-foreground"
                      @click="removeTopic(topic)"
                    >
                      <UIcon name="i-lucide-x" class="size-3" />
                    </button>
                  </span>
                </div>
              </div>

              <!-- Updated At -->
              <div v-if="selectedMemory.updated_at" class="space-y-1">
                <label class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  {{ t("memory.updatedAt") }}
                </label>
                <p class="font-mono text-sm text-foreground">
                  {{ formatDateTime(selectedMemory.updated_at) }}
                </p>
              </div>
            </div>

            <!-- Detail Footer -->
            <div
              class="flex items-center justify-between border-t border-default px-4 py-3"
            >
              <UButton
                color="error"
                variant="outline"
                size="sm"
                :disabled="saving || deleting"
                @click="deleteConfirmOpen = true"
              >
                {{ t("common.delete") }}
              </UButton>

              <div class="flex items-center gap-2">
                <UButton
                  color="neutral"
                  variant="outline"
                  size="sm"
                  :disabled="saving"
                  @click="cancelDetail"
                >
                  {{ t("common.cancel") }}
                </UButton>
                <UButton
                  color="primary"
                  size="sm"
                  :loading="saving"
                  :disabled="saving || !editContent.trim()"
                  @click="void saveMemory()"
                >
                  {{ t("common.save") }}
                </UButton>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- Create Memory Dialog -->
      <UModal
        v-model:open="createDialogOpen"
        :title="t('memory.createMemory')"
      >
        <template #body>
          <UForm
            id="create-memory-form"
            :schema="createSchema"
            :state="createFormState"
            class="space-y-5"
            @submit="onCreateSubmit"
          >
            <UFormField :label="t('memory.userId')" name="user_id" required>
              <UInput
                v-model="createFormState.user_id"
                :placeholder="t('memory.userIdPlaceholder')"
                icon="i-lucide-user"
                class="w-full"
              />
            </UFormField>

            <UFormField :label="t('memory.content')" name="memory" required>
              <UTextarea
                v-model="createFormState.memory"
                :placeholder="t('memory.contentPlaceholder')"
                :rows="3"
                autoresize
                class="w-full"
              />
            </UFormField>

            <UFormField :label="t('memory.topicsOptional')" name="topicInput">
              <div class="w-full space-y-2">
                <div class="flex items-center gap-2">
                  <UInput
                    v-model="createFormState.topicInput"
                    :placeholder="t('memory.topicsPlaceholder')"
                    icon="i-lucide-tag"
                    class="flex-1"
                    @keydown="handleCreateTopicKeydown"
                  />
                  <UButton
                    color="neutral"
                    variant="outline"
                    square
                    icon="i-lucide-plus"
                    type="button"
                    @click="addCreateTopic"
                  />
                </div>
                <div v-if="createTopics.length" class="flex flex-wrap gap-1.5">
                  <UBadge
                    v-for="topic in createTopics"
                    :key="topic"
                    color="neutral"
                    variant="subtle"
                    class="gap-1 pr-1"
                  >
                    {{ topic }}
                    <UButton
                      color="neutral"
                      variant="link"
                      size="2xs"
                      square
                      icon="i-lucide-x"
                      type="button"
                      class="size-4"
                      @click="removeCreateTopic(topic)"
                    />
                  </UBadge>
                </div>
              </div>
            </UFormField>
          </UForm>
        </template>

        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="outline"
              :disabled="creating"
              @click="createDialogOpen = false"
            >
              {{ t("common.cancel") }}
            </UButton>
            <UButton
              color="primary"
              type="submit"
              form="create-memory-form"
              :loading="creating"
              :disabled="creating"
            >
              {{ t("memory.create") }}
            </UButton>
          </div>
        </template>
      </UModal>

      <!-- Single Delete Confirm Modal -->
      <UModal
        v-model:open="deleteConfirmOpen"
        :title="t('memory.deleteTitle')"
        :description="t('memory.deleteHint')"
        :close="false"
      >
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="outline"
              type="button"
              :disabled="deleting"
              @click="deleteConfirmOpen = false"
            >
              {{ t("common.cancel") }}
            </UButton>
            <UButton
              color="error"
              type="button"
              :loading="deleting"
              :disabled="deleting"
              @click="void confirmDeleteMemory()"
            >
              {{ t("common.delete") }}
            </UButton>
          </div>
        </template>
      </UModal>

      <!-- Batch Delete Confirm Modal -->
      <UModal
        v-model:open="batchDeleteConfirmOpen"
        :title="t('memory.deleteBatchTitle', { count: selectedCount })"
        :description="t('memory.deleteHint')"
        :close="false"
      >
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="outline"
              type="button"
              :disabled="batchDeleting"
              @click="batchDeleteConfirmOpen = false"
            >
              {{ t("common.cancel") }}
            </UButton>
            <UButton
              color="error"
              type="button"
              :loading="batchDeleting"
              :disabled="batchDeleting"
              @click="void confirmBatchDelete()"
            >
              {{ batchDeleting ? t("memory.deleting") : t("common.delete") }}
            </UButton>
          </div>
        </template>
      </UModal>
    </div>
  </div>
</template>
