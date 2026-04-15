<script setup lang="ts">
import type { TableColumn } from "@nuxt/ui"
import type { TableRow } from "@nuxt/ui"
import { h, computed, onMounted, onUnmounted, ref, resolveComponent, watch } from "vue"
import { useI18n } from "vue-i18n"
import { useAppState } from "@/composables/store"
import { getAgentOsBaseUrl } from "@/composables/request"
import {
  listContentAPI,
  uploadContentAPI,
  updateContentAPI,
  deleteContentAPI,
} from "@/api/knowledge"
import knowledgeConfig from "@/assets/knowledge_config.json"
import type { KnowledgeContent } from "@/api/knowledge"

const { t } = useI18n()
const toast = useToast()
const app = useAppState()

const UCheckbox = resolveComponent("UCheckbox")

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

function formatDateTime(raw?: string | null) {
  if (!raw) return "—"
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return raw
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function contentTypeLabel(type?: string | null) {
  if (!type) return "—"
  const t = type.toLowerCase()
  if (t.includes("web") || t.includes("url")) return "Web"
  if (t.includes("pdf")) return "PDF"
  if (t.includes("docx") || t.includes("word") || t.includes("msword")) return "Word"
  if (t.includes("pptx") || t.includes("presentation") || t.includes("powerpoint")) return "PPT"
  if (t.includes("xlsx") || t.includes("spreadsheet") || t.includes("excel")) return "Excel"
  if (t.includes("csv")) return "CSV"
  if (t.includes("markdown") || t === "md") return "Markdown"
  if (t.includes("html") || t.includes("xhtml")) return "HTML"
  if (t.includes("image") || ["png", "jpg", "jpeg", "tiff", "bmp", "webp"].some((e) => t.includes(e))) return "Image"
  if (t.includes("audio") || ["wav", "mp3", "m4a", "aac", "ogg", "flac"].some((e) => t.includes(e))) return "Audio"
  if (t.includes("video") || ["mp4", "avi", "mov"].some((e) => t.includes(e))) return "Video"
  if (t.includes("json")) return "JSON"
  if (t.includes("xml")) return "XML"
  if (t.includes("vtt")) return "VTT"
  if (t.includes("latex") || t.includes("tex")) return "LaTeX"
  if (t.includes("asciidoc")) return "AsciiDoc"
  if (t.includes("text") || t.includes("txt")) return "Text"
  return type
}

function contentTypeIcon(type?: string | null): string {
  if (!type) return "i-lucide-file"
  const t = type.toLowerCase()
  if (t.includes("web") || t.includes("url")) return "i-lucide-globe"
  if (t.includes("pdf")) return "i-lucide-file-text"
  if (t.includes("docx") || t.includes("word") || t.includes("msword")) return "i-lucide-file-pen"
  if (t.includes("pptx") || t.includes("presentation") || t.includes("powerpoint")) return "i-lucide-presentation"
  if (t.includes("xlsx") || t.includes("spreadsheet") || t.includes("excel")) return "i-lucide-file-spreadsheet"
  if (t.includes("csv")) return "i-lucide-table"
  if (t.includes("markdown") || t === "md") return "i-lucide-file-code"
  if (t.includes("html") || t.includes("xhtml")) return "i-lucide-globe"
  if (t.includes("image") || ["png", "jpg", "jpeg", "tiff", "bmp", "webp"].some((e) => t.includes(e))) return "i-lucide-image"
  if (t.includes("audio") || ["wav", "mp3", "m4a", "aac", "ogg", "flac"].some((e) => t.includes(e))) return "i-lucide-music"
  if (t.includes("video") || ["mp4", "avi", "mov"].some((e) => t.includes(e))) return "i-lucide-video"
  if (t.includes("json")) return "i-lucide-braces"
  if (t.includes("xml")) return "i-lucide-code"
  if (t.includes("vtt")) return "i-lucide-captions"
  if (t.includes("latex") || t.includes("tex")) return "i-lucide-file-text"
  if (t.includes("asciidoc")) return "i-lucide-file-text"
  if (t.includes("text") || t.includes("txt")) return "i-lucide-file-text"
  return "i-lucide-file"
}

function contentTypeIconColor(type?: string | null): string {
  if (!type) return "text-muted-foreground"
  const t = type.toLowerCase()
  if (t.includes("web") || t.includes("url") || t.includes("html") || t.includes("xhtml")) return "text-red-500"
  if (t.includes("pdf")) return "text-red-600 dark:text-red-400"
  if (t.includes("docx") || t.includes("word") || t.includes("msword")) return "text-blue-600 dark:text-blue-400"
  if (t.includes("pptx") || t.includes("presentation") || t.includes("powerpoint")) return "text-orange-500 dark:text-orange-400"
  if (t.includes("xlsx") || t.includes("spreadsheet") || t.includes("excel") || t.includes("csv")) return "text-green-600 dark:text-green-400"
  if (t.includes("markdown") || t === "md") return "text-gray-600 dark:text-gray-400"
  if (t.includes("image") || ["png", "jpg", "jpeg", "tiff", "bmp", "webp"].some((e) => t.includes(e))) return "text-purple-500 dark:text-purple-400"
  if (t.includes("audio") || ["wav", "mp3", "m4a", "aac", "ogg", "flac"].some((e) => t.includes(e))) return "text-pink-500 dark:text-pink-400"
  if (t.includes("video") || ["mp4", "avi", "mov"].some((e) => t.includes(e))) return "text-indigo-500 dark:text-indigo-400"
  if (t.includes("json")) return "text-yellow-600 dark:text-yellow-400"
  if (t.includes("xml")) return "text-orange-600 dark:text-orange-400"
  if (t.includes("vtt")) return "text-teal-500 dark:text-teal-400"
  if (t.includes("latex") || t.includes("tex") || t.includes("asciidoc")) return "text-stone-600 dark:text-stone-400"
  if (t.includes("text") || t.includes("txt")) return "text-gray-500 dark:text-gray-400"
  return "text-muted-foreground"
}

function statusIcon(status?: string | null) {
  switch (status) {
    case "completed":
      return "i-lucide-check"
    case "processing":
      return "i-lucide-loader"
    case "pending":
      return "i-lucide-clock"
    case "failed":
      return "i-lucide-x"
    default:
      return "i-lucide-minus"
  }
}

function statusColor(status?: string | null): string {
  switch (status) {
    case "completed":
      return "text-green-600 dark:text-green-400"
    case "processing":
      return "text-blue-600 dark:text-blue-400"
    case "pending":
      return "text-yellow-600 dark:text-yellow-400"
    case "failed":
      return "text-red-600 dark:text-red-400"
    default:
      return "text-muted-foreground"
  }
}

function statusLabel(status?: string | null) {
  switch (status) {
    case "completed":
      return t("knowledge.statusCompleted")
    case "processing":
      return t("knowledge.statusProcessing")
    case "pending":
      return t("knowledge.statusPending")
    case "failed":
      return t("knowledge.statusFailed")
    default:
      return "—"
  }
}

// --- Content list ---

const contents = ref<KnowledgeContent[]>([])
const loadingContents = ref(false)
const errorMessage = ref<string | null>(null)
const sortDesc = ref(true)

async function refreshContents() {
  const { base, token } = authHeaders()
  if (!base || !token) return
  loadingContents.value = true
  errorMessage.value = null
  try {
    const res = await listContentAPI(base, token, {
      limit: 100,
      sort_by: "updated_at",
      sort_order: sortDesc.value ? "desc" : "asc",
    })
    if (!res.ok) {
      errorMessage.value = t("knowledge.loadFailed", { message: res.message })
      contents.value = []
      return
    }
    contents.value = res.data.data
    const alive = new Set(res.data.data.map((c: KnowledgeContent) => c.id))
    const next = { ...rowSelection.value }
    for (const k of Object.keys(next)) {
      if (!alive.has(k)) delete next[k]
    }
    rowSelection.value = next
  } finally {
    loadingContents.value = false
  }
}

// --- Detail panel ---

const selectedContent = ref<KnowledgeContent | null>(null)
const editName = ref("")
const editDescription = ref("")
const editMetadata = ref<{ key: string; value: string }[]>([])
const saving = ref(false)
const deleting = ref(false)
const deleteConfirmOpen = ref(false)

// --- Batch selection ---
const rowSelection = ref<Record<string, boolean>>({})
const batchDeleteConfirmOpen = ref(false)

const selectedIds = computed(() =>
  Object.keys(rowSelection.value).filter((k) => rowSelection.value[k]),
)
const selectedCount = computed(() => selectedIds.value.length)

function clearSelection() {
  rowSelection.value = {}
  batchDeleteConfirmOpen.value = false
}

function openBatchDeleteConfirm() {
  if (!selectedIds.value.length || deleting.value) return
  batchDeleteConfirmOpen.value = true
}

async function confirmBatchDelete() {
  if (!selectedIds.value.length || deleting.value) return
  const { base, token } = authHeaders()
  if (!base || !token) return
  deleting.value = true
  const ids = [...selectedIds.value]
  try {
    for (const id of ids) {
      const res = await deleteContentAPI(base, token, id)
      if (!res.ok) {
        toast.add({ title: t("knowledge.deleteFailed", { message: res.message }), color: "error" })
        return
      }
    }
    toast.add({ title: t("knowledge.deleted"), color: "success" })
    rowSelection.value = {}
    batchDeleteConfirmOpen.value = false
    if (selectedContent.value && ids.includes(selectedContent.value.id)) {
      selectedContent.value = null
    }
    await refreshContents()
  } finally {
    deleting.value = false
  }
}

function selectContentRow(_e: Event, row: TableRow<KnowledgeContent>) {
  const item = row.original
  selectedContent.value = { ...item }
  editName.value = item.name ?? ""
  editDescription.value = item.description ?? ""
  editMetadata.value = item.metadata
    ? Object.entries(item.metadata)
        .filter(([key, value]) => !key.startsWith("_") && value != null)
        .map(([key, value]) => ({
          key,
          value: typeof value === "string" ? value : JSON.stringify(value),
        }))
    : []
}

const metaKeyInput = ref("")
const metaValueInput = ref("")

function addMetadataTag() {
  const k = metaKeyInput.value.trim()
  const v = metaValueInput.value.trim()
  if (!k) return
  editMetadata.value.push({ key: k, value: v })
  metaKeyInput.value = ""
  metaValueInput.value = ""
}

function removeMetadataTag(index: number) {
  editMetadata.value.splice(index, 1)
}

function closeDetail() {
  selectedContent.value = null
}

async function saveContent() {
  if (!selectedContent.value) return
  const { base, token } = authHeaders()
  if (!base || !token) return
  saving.value = true
  try {
    const meta: Record<string, string | null> = {}
    if (selectedContent.value.metadata) {
      for (const k of Object.keys(selectedContent.value.metadata)) {
        if (!k.startsWith("_")) meta[k] = null
      }
    }
    for (const { key, value } of editMetadata.value) {
      if (key.trim()) meta[key.trim()] = value
    }
    const res = await updateContentAPI(base, token, selectedContent.value.id, {
      name: editName.value,
      description: editDescription.value,
      metadata: JSON.stringify(meta),
    })
    if (!res.ok) {
      toast.add({ title: t("knowledge.saveFailed", { message: res.message }), color: "error" })
      return
    }
    toast.add({ title: t("knowledge.saved"), color: "success" })
    selectedContent.value = null
    await refreshContents()
  } finally {
    saving.value = false
  }
}

async function confirmDeleteContent() {
  if (!selectedContent.value) return
  const { base, token } = authHeaders()
  if (!base || !token) return
  deleting.value = true
  try {
    const res = await deleteContentAPI(base, token, selectedContent.value.id)
    if (!res.ok) {
      toast.add({ title: t("knowledge.deleteFailed", { message: res.message }), color: "error" })
      return
    }
    toast.add({ title: t("knowledge.deleted"), color: "success" })
    selectedContent.value = null
    deleteConfirmOpen.value = false
    await refreshContents()
  } finally {
    deleting.value = false
  }
}

// --- Columns ---

const contentColumns = computed<TableColumn<KnowledgeContent>[]>(() => [
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
        "aria-label": t("knowledge.selectAll"),
      }),
    cell: ({ row }) =>
      h(UCheckbox, {
        "modelValue": row.getIsSelected(),
        "onUpdate:modelValue": (value: boolean | "indeterminate") =>
          row.toggleSelected(!!value),
        "aria-label": t("knowledge.selectRow", {
          name: row.original.name ?? "",
        }),
      }),
    enableSorting: false,
    enableHiding: false,
  },
  {
    accessorKey: "name",
    header: t("knowledge.colName"),
    meta: {
      class: {
        th: "min-w-0 w-[32%]",
        td: "max-w-0 min-w-0",
      },
    },
    cell: ({ row }) =>
      h(
        "span",
        {
          class:
            "block min-w-0 truncate text-sm font-normal text-foreground",
          title: row.original.name ?? "",
        },
        row.original.name ?? "—",
      ),
  },
  {
    id: "content_type",
    accessorFn: (row) => row.type ?? "",
    header: t("knowledge.colContentType"),
    meta: {
      class: {
        th: "w-[15%]",
        td: "text-sm text-muted-foreground",
      },
    },
    cell: ({ row }) => {
      const rawType = row.original.type
      return h("div", { class: "flex items-center gap-1.5" }, [
        h(resolveComponent("UIcon"), {
          name: contentTypeIcon(rawType),
          class: `size-4 shrink-0 ${contentTypeIconColor(rawType)}`,
        }),
        h("span", {}, contentTypeLabel(rawType)),
      ])
    },
  },
  {
    id: "metadata",
    accessorFn: (row) =>
      row.metadata
        ? Object.keys(row.metadata).filter((k) => !k.startsWith("_")).join(", ")
        : "",
    header: t("knowledge.colMetadata"),
    meta: {
      class: {
        th: "w-[15%]",
        td: "max-w-0 min-w-0 text-sm text-muted-foreground",
      },
    },
    cell: ({ row }) => {
      const meta = row.original.metadata
      const entries = meta
        ? Object.entries(meta).filter(([k]) => !k.startsWith("_"))
        : []
      if (entries.length === 0)
        return h("span", { class: "text-muted-foreground" }, "—")
      const text = entries
        .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
        .join(", ")
      return h(
        "span",
        { class: "block truncate", title: text },
        text,
      )
    },
  },
  {
    id: "status",
    accessorFn: (row) => row.status ?? "",
    header: t("knowledge.colStatus"),
    meta: {
      class: {
        th: "w-[12%]",
        td: "text-sm",
      },
    },
    cell: ({ row }) => {
      const s = row.original.status
      const spinning = s === "processing" || s === "pending"
      return h("div", { class: `flex items-center gap-1 ${statusColor(s)}` }, [
        h(resolveComponent("UIcon"), {
          name: statusIcon(s),
          class: spinning ? "size-4 animate-spin" : "size-4",
        }),
        h("span", { class: "text-xs font-medium uppercase" }, statusLabel(s)),
      ])
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
          label: t("knowledge.colUpdatedAt"),
          icon: sortDesc.value
            ? "i-lucide-arrow-down-wide-narrow"
            : "i-lucide-arrow-up-narrow-wide",
          class: "-mx-2.5 text-xs font-semibold uppercase tracking-wider",
          onClick: () => {
            sortDesc.value = !sortDesc.value
            void refreshContents()
          },
        }),
      ]),
    cell: ({ row }) => formatDateTime(row.original.updated_at),
    meta: {
      class: {
        th: "text-right w-[20%]",
        td: "text-right text-sm whitespace-nowrap tabular-nums text-muted-foreground",
      },
    },
  },
])

const contentTableMeta = computed(() => ({
  class: {
    tr: (row: { original: KnowledgeContent }) =>
      [
        "cursor-pointer transition-colors",
        selectedContent.value &&
        row.original?.id === selectedContent.value.id
          ? "[&_td:not(:first-child)]:!text-primary [&_td:not(:first-child)_span]:!text-primary"
          : "",
      ]
        .filter(Boolean)
        .join(" "),
  },
}))

const tableUi = {
  root: "overflow-x-auto",
  base: "min-w-full table-fixed",
  thead: "bg-elevated/40",
  th: "border-b border-default py-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground",
  tbody: "divide-y divide-default",
  tr: "odd:bg-default even:bg-elevated/30 data-[selected=true]:bg-primary/10 hover:bg-elevated/45 cursor-pointer dark:even:bg-white/[0.06]",
  td: "py-3 px-3 text-sm align-middle",
  separator: "hidden",
  empty: "py-8 text-sm text-muted-foreground",
  loading: "py-8 text-sm",
}

watch(selectedCount, (n) => {
  if (n === 0) batchDeleteConfirmOpen.value = false
})

// --- Add Content dialog ---

const addDialogOpen = ref(false)

function openAddDialog() {
  resetFileForm()
  resetWebForm()
  addDialogOpen.value = true
}

// File upload
interface FileUploadItem {
  file: File
  selected: boolean
  expanded: boolean
  name: string
  description: string
  readerId: string
  chunkingEnabled: boolean
  chunkerId: string
  chunkSize: number
  chunkOverlap: number
  metadata: { key: string; value: string }[]
  metaKeyInput: string
  metaValueInput: string
}

const fileItems = ref<FileUploadItem[]>([])
const uploadingFile = ref(false)

function resetFileForm() {
  fileItems.value = []
}

function createFileItem(file: File): FileUploadItem {
  return {
    file,
    selected: false,
    expanded: false,
    name: file.name,
    description: "",
    readerId: cfgReader.id,
    chunkingEnabled: false,
    chunkerId: chunkerItems.length > 0 ? chunkerItems[0].id : "",
    chunkSize: 5000,
    chunkOverlap: 0,
    metadata: [],
    metaKeyInput: "",
    metaValueInput: "",
  }
}

function onFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files) {
    for (const f of Array.from(input.files)) {
      if (!fileItems.value.some((x) => x.file.name === f.name)) {
        fileItems.value.push(createFileItem(f))
      }
    }
    input.value = ""
  }
}

function onFileDrop(e: DragEvent) {
  e.preventDefault()
  if (e.dataTransfer?.files) {
    for (const f of Array.from(e.dataTransfer.files)) {
      if (!fileItems.value.some((x) => x.file.name === f.name)) {
        fileItems.value.push(createFileItem(f))
      }
    }
  }
}

function removeFileItem(index: number) {
  fileItems.value.splice(index, 1)
}

function toggleFileItemExpand(index: number) {
  fileItems.value[index].expanded = !fileItems.value[index].expanded
}

function addFileItemMeta(item: FileUploadItem) {
  const k = item.metaKeyInput.trim()
  const v = item.metaValueInput.trim()
  if (!k) return
  item.metadata.push({ key: k, value: v })
  item.metaKeyInput = ""
  item.metaValueInput = ""
}

function removeFileItemMeta(item: FileUploadItem, metaIndex: number) {
  item.metadata.splice(metaIndex, 1)
}

function appendUploadFields(fd: FormData, item: FileUploadItem | WebUrlItem) {
  if (item.name.trim()) fd.append("name", item.name.trim())
  if (item.description.trim()) fd.append("description", item.description.trim())
  if (item.readerId) fd.append("reader_id", item.readerId)
  if (item.chunkingEnabled && item.chunkerId) {
    fd.append("chunker_id", item.chunkerId)
    if (chunkerHasSize(item.chunkerId)) fd.append("chunk_size", String(item.chunkSize))
    if (chunkerHasOverlap(item.chunkerId)) fd.append("chunk_overlap", String(item.chunkOverlap))
  }
  const meta: Record<string, string> = {}
  for (const { key, value } of item.metadata) {
    if (key.trim()) meta[key.trim()] = value
  }
  if (Object.keys(meta).length) fd.append("metadata", JSON.stringify(meta))
}

async function submitAll() {
  const { base, token } = authHeaders()
  if (!base || !token) return
  uploadingFile.value = true
  try {
    for (const item of fileItems.value) {
      const fd = new FormData()
      fd.append("file", item.file)
      appendUploadFields(fd, item)
      const res = await uploadContentAPI(base, token, fd)
      if (!res.ok) {
        toast.add({ title: t("knowledge.createFailed", { message: res.message }), color: "error" })
        return
      }
    }
    for (const item of webItems.value) {
      const fd = new FormData()
      fd.append("url", item.url)
      appendUploadFields(fd, item)
      const res = await uploadContentAPI(base, token, fd)
      if (!res.ok) {
        toast.add({ title: t("knowledge.createFailed", { message: res.message }), color: "error" })
        return
      }
    }
    toast.add({ title: t("knowledge.created"), color: "success" })
    addDialogOpen.value = false
    await refreshContents()
  } finally {
    uploadingFile.value = false
  }
}

// Web upload
interface WebUrlItem {
  url: string
  selected: boolean
  expanded: boolean
  name: string
  description: string
  readerId: string
  chunkingEnabled: boolean
  chunkerId: string
  chunkSize: number
  chunkOverlap: number
  metadata: { key: string; value: string }[]
  metaKeyInput: string
  metaValueInput: string
}

const webUrlInput = ref("")
const webItems = ref<WebUrlItem[]>([])
const allSelectedCount = computed(() =>
  fileItems.value.filter((i) => i.selected).length +
  webItems.value.filter((i) => i.selected).length,
)
const allItemsCount = computed(() => fileItems.value.length + webItems.value.length)

function resetWebForm() {
  webUrlInput.value = ""
  webItems.value = []
}

function addWebUrl() {
  const val = webUrlInput.value.trim()
  if (!val) return
  if (webItems.value.some((i) => i.url === val)) return
  webItems.value.push({
    url: val,
    selected: false,
    expanded: false,
    name: val,
    description: "",
    readerId: cfgReader.id,
    chunkingEnabled: false,
    chunkerId: chunkerItems.length > 0 ? chunkerItems[0].id : "",
    chunkSize: 5000,
    chunkOverlap: 0,
    metadata: [],
    metaKeyInput: "",
    metaValueInput: "",
  })
  webUrlInput.value = ""
}

function removeWebItem(index: number) {
  webItems.value.splice(index, 1)
}

function toggleWebItemExpand(index: number) {
  webItems.value[index].expanded = !webItems.value[index].expanded
}

function addWebItemMeta(item: WebUrlItem) {
  const k = item.metaKeyInput.trim()
  const v = item.metaValueInput.trim()
  if (!k) return
  item.metadata.push({ key: k, value: v })
  item.metaKeyInput = ""
  item.metaValueInput = ""
}

function removeWebItemMeta(item: WebUrlItem, metaIndex: number) {
  item.metadata.splice(metaIndex, 1)
}

// Config (from local JSON)
const cfgReader = knowledgeConfig.reader
const cfgChunkers = knowledgeConfig.chunkers

const readerItem = {
  id: cfgReader.id,
  label: cfgReader.name,
  _description: cfgReader.description,
}

const allowedChunkerIds = new Set(cfgReader.chunkers)

const chunkerItems = Object.values(cfgChunkers)
  .filter((c) => allowedChunkerIds.has(c.key))
  .map((c) => {
    const descKey = `knowledge.chunkerDesc.${c.key}`
    const desc = t(descKey)
    return {
      id: c.key,
      label: c.name,
      _description: desc !== descKey ? desc : c.description,
    }
  })

function chunkerHasSize(chunkerId: string) {
  const meta = cfgChunkers[chunkerId as keyof typeof cfgChunkers]?.metadata
  return meta != null && "chunk_size" in meta
}

function chunkerHasOverlap(chunkerId: string) {
  const meta = cfgChunkers[chunkerId as keyof typeof cfgChunkers]?.metadata
  return meta != null && "chunk_overlap" in meta
}

// --- Auto-poll when items are processing/pending ---

const hasUnfinishedItems = computed(() =>
  contents.value.some((c) => c.status === "processing" || c.status === "pending"),
)

let pollTimer: ReturnType<typeof setTimeout> | null = null

async function pollContents() {
  const { base, token } = authHeaders()
  if (!base || !token) return
  try {
    const res = await listContentAPI(base, token, {
      limit: 100,
      sort_by: "updated_at",
      sort_order: sortDesc.value ? "desc" : "asc",
    })
    if (!res.ok) return
    contents.value = res.data.data
    const alive = new Set(res.data.data.map((c: KnowledgeContent) => c.id))
    const next = { ...rowSelection.value }
    for (const k of Object.keys(next)) {
      if (!alive.has(k)) delete next[k]
    }
    rowSelection.value = next
  } catch {
    // silent
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setTimeout(async () => {
    await pollContents()
    if (hasUnfinishedItems.value) {
      startPolling()
    }
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

watch(hasUnfinishedItems, (val) => {
  if (val) {
    startPolling()
  } else {
    stopPolling()
  }
})

onMounted(() => {
  if (hasOsAuth.value) {
    void refreshContents()
  }
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="mx-auto flex w-full max-w-7xl flex-col gap-5 p-4 sm:p-6">
    <UAlert
      v-if="errorMessage"
      color="error"
      icon="i-lucide-alert-circle"
      :title="errorMessage"
      :close-icon="'i-lucide-x'"
      @close="errorMessage = null"
    />

    <UAlert
      v-if="!hasOsAuth"
      color="info"
      icon="i-lucide-info"
      :description="t('knowledge.needLogin')"
    />

    <template v-else>
      <div
        class="flex gap-4"
        :class="selectedContent ? 'flex-col lg:flex-row' : ''"
      >
        <!-- Content List -->
        <div
          class="overflow-hidden rounded-lg border border-default bg-default shadow-sm"
          :class="selectedContent ? 'lg:w-1/2' : 'w-full'"
        >
          <div
            class="flex min-h-12 flex-nowrap items-center justify-between gap-3 border-b border-default px-3 py-3 sm:min-h-14 sm:px-4 sm:py-3.5"
          >
            <span class="shrink-0 text-xs text-muted-foreground">
              {{
                loadingContents
                  ? t("common.loading")
                  : t("common.itemsInTable", { count: contents.length })
              }}
            </span>
            <div class="flex shrink-0 items-center justify-end gap-2 sm:gap-3">
              <template v-if="selectedCount === 0">
                <UButton
                  color="primary"
                  variant="solid"
                  size="sm"
                  icon="i-lucide-plus"
                  :label="t('knowledge.addContent')"
                  @click="openAddDialog"
                />
                <UButton
                  color="neutral"
                  variant="outline"
                  size="sm"
                  square
                  icon="i-lucide-refresh-cw"
                  :aria-label="t('common.refresh')"
                  :title="t('common.refresh')"
                  :disabled="loadingContents"
                  :loading="loadingContents"
                  class="shrink-0"
                  @click="void refreshContents()"
                />
              </template>
              <template v-if="selectedCount > 0 && !batchDeleteConfirmOpen">
                <span
                  class="shrink-0 text-xs tabular-nums text-muted-foreground"
                  role="status"
                  aria-live="polite"
                >
                  {{ t("knowledge.selectedCount", { count: selectedCount }) }}
                </span>
                <UButton
                  variant="outline"
                  color="neutral"
                  size="sm"
                  type="button"
                  class="shrink-0"
                  :disabled="deleting"
                  @click="clearSelection"
                >
                  {{ t("common.cancel") }}
                </UButton>
                <UButton
                  type="button"
                  color="error"
                  variant="solid"
                  size="sm"
                  class="shrink-0"
                  :disabled="deleting"
                  @click="openBatchDeleteConfirm"
                >
                  {{ t("common.delete") }}
                </UButton>
              </template>
            </div>
          </div>

          <UTable
            v-model:row-selection="rowSelection"
            :data="contents"
            :columns="contentColumns"
            :loading="loadingContents"
            :get-row-id="(row: KnowledgeContent) => row.id"
            :empty="t('knowledge.emptyContent')"
            sticky="header"
            class="w-full min-w-0"
            :ui="tableUi"
            :meta="contentTableMeta"
            @select="selectContentRow"
          >
            <template #loading>
              <span class="text-muted-foreground">{{
                t("common.loading")
              }}</span>
            </template>
          </UTable>
        </div>

        <!-- Detail Panel -->
        <div
          v-if="selectedContent"
          class="overflow-hidden rounded-lg border border-default bg-default shadow-sm lg:w-1/2"
        >
          <div class="flex items-center justify-between border-b border-default px-4 py-3">
            <h3
              class="min-w-0 truncate text-base font-semibold"
              :title="selectedContent.name ?? ''"
            >
              {{ selectedContent.name ?? "—" }}
            </h3>
            <UButton
              color="neutral"
              variant="ghost"
              size="sm"
              icon="i-lucide-x"
              @click="closeDetail"
            />
          </div>

          <div class="space-y-5 p-4">
            <!-- Name -->
            <div>
              <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                <UIcon name="i-lucide-type" class="size-4" />
                {{ t("knowledge.name") }}
              </label>
              <UInput v-model="editName" class="w-full" />
            </div>

            <!-- Description -->
            <div>
              <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                <UIcon name="i-lucide-align-left" class="size-4" />
                {{ t("knowledge.descriptionOptional") }}
              </label>
              <UTextarea
                v-model="editDescription"
                :placeholder="t('knowledge.descriptionPlaceholder')"
                :rows="3"
                class="w-full"
              />
            </div>

            <!-- Metadata -->
            <div>
              <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                <UIcon name="i-lucide-tags" class="size-4" />
                {{ t("knowledge.metadata") }}
              </label>
              <div class="flex items-center gap-2">
                <UInput
                  v-model="metaKeyInput"
                  :placeholder="t('knowledge.metadataKey')"
                  class="flex-1"
                  @keydown.enter.prevent="addMetadataTag"
                />
                <span class="text-muted-foreground">=</span>
                <UInput
                  v-model="metaValueInput"
                  :placeholder="t('knowledge.metadataValue')"
                  class="flex-1"
                  @keydown.enter.prevent="addMetadataTag"
                />
                <UButton
                  color="neutral"
                  variant="ghost"
                  size="sm"
                  icon="i-lucide-plus"
                  :disabled="!metaKeyInput.trim()"
                  @click="addMetadataTag"
                />
              </div>
              <div v-if="editMetadata.length" class="mt-2 flex flex-wrap gap-1.5">
                <UBadge
                  v-for="(row, i) in editMetadata"
                  :key="i"
                  color="neutral"
                  variant="subtle"
                  size="md"
                  class="gap-1 pl-2 pr-1"
                >
                  {{ row.key }} = {{ row.value }}
                  <UButton
                    color="neutral"
                    variant="link"
                    size="xs"
                    icon="i-lucide-x"
                    class="ml-0.5 size-4"
                    @click="removeMetadataTag(i)"
                  />
                </UBadge>
              </div>
            </div>

            <!-- Content Type -->
            <div>
              <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                <UIcon :name="contentTypeIcon(selectedContent.type)" class="size-4" />
                {{ t("knowledge.contentType") }}
              </label>
              <div class="flex items-center gap-2 rounded-md bg-muted px-3 py-2 text-sm">
                <UIcon
                  :name="contentTypeIcon(selectedContent.type)"
                  :class="['size-4 shrink-0', contentTypeIconColor(selectedContent.type)]"
                />
                {{ contentTypeLabel(selectedContent.type) }}
              </div>
            </div>

            <!-- Updated At -->
            <div>
              <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                <UIcon name="i-lucide-calendar" class="size-4" />
                {{ t("knowledge.updatedAt") }}
              </label>
              <div class="rounded-md bg-muted px-3 py-2 font-mono text-sm">
                {{ formatDateTime(selectedContent.updated_at) }}
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex items-center justify-between border-t border-default px-4 py-3">
            <UButton
              color="error"
              variant="outline"
              size="sm"
              :loading="deleting"
              @click="deleteConfirmOpen = true"
            >
              {{ t("common.delete") }}
            </UButton>
            <div class="flex gap-2">
              <UButton
                color="neutral"
                variant="outline"
                size="sm"
                @click="closeDetail"
              >
                {{ t("common.cancel") }}
              </UButton>
              <UButton
                color="primary"
                variant="solid"
                size="sm"
                :loading="saving"
                @click="saveContent"
              >
                {{ t("knowledge.save") }}
              </UButton>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Single Delete Confirm Modal -->
    <UModal
      v-model:open="deleteConfirmOpen"
      :title="t('knowledge.deleteTitle')"
      :description="t('knowledge.deleteHint')"
      :close="false"
    >
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            color="neutral"
            variant="outline"
            @click="deleteConfirmOpen = false"
          >
            {{ t("common.cancel") }}
          </UButton>
          <UButton
            color="error"
            variant="solid"
            :loading="deleting"
            @click="confirmDeleteContent"
          >
            {{ t("common.delete") }}
          </UButton>
        </div>
      </template>
    </UModal>

    <!-- Batch Delete Confirm Modal -->
    <UModal
      v-model:open="batchDeleteConfirmOpen"
      :title="t('knowledge.deleteBatchTitle', { count: selectedCount })"
      :description="t('knowledge.deleteHint')"
      :close="false"
    >
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            color="neutral"
            variant="outline"
            type="button"
            :disabled="deleting"
            @click="batchDeleteConfirmOpen = false"
          >
            {{ t("common.cancel") }}
          </UButton>
          <UButton
            color="error"
            type="button"
            :loading="deleting"
            :disabled="deleting"
            @click="void confirmBatchDelete()"
          >
            {{ deleting ? t("knowledge.deleting") : t("common.delete") }}
          </UButton>
        </div>
      </template>
    </UModal>

    <!-- Add Content Modal (fullscreen) -->
    <UModal
      v-model:open="addDialogOpen"
      :title="t('knowledge.addFileTitle')"
      :description="t('knowledge.addFileHint')"
      :close="true"
      fullscreen
    >
      <template #body>
        <div class="flex flex-1 gap-4">
          <!-- Left: File upload + URL input -->
          <div class="flex w-2/5 flex-col gap-4">
            <!-- Drag & Drop area -->
            <div
              class="flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-default p-8 text-center"
              @drop="onFileDrop"
              @dragover.prevent
            >
              <UIcon name="i-lucide-folder-open" class="size-8 text-muted-foreground" />
              <span class="text-sm text-muted-foreground">{{ t("knowledge.dragDrop") }}</span>
              <label>
                <UButton color="neutral" variant="outline" size="sm" as="span">
                  {{ t("knowledge.selectFile") }}
                </UButton>
                <input type="file" multiple class="hidden" @change="onFileSelect" />
              </label>
            </div>

            <div class="flex items-center gap-2 text-xs text-muted-foreground">
              <div class="flex-1 border-t border-default" />
              {{ t("knowledge.or") }}
              <div class="flex-1 border-t border-default" />
            </div>

            <!-- Web URL input -->
            <div>
              <span class="mb-1 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {{ t("knowledge.enterWebUrl") }}
              </span>
              <div class="flex items-center gap-2">
                <UInput
                  v-model="webUrlInput"
                  :placeholder="t('knowledge.webUrlPlaceholder')"
                  class="flex-1"
                  @keydown.enter="addWebUrl"
                />
                <UButton
                  color="neutral"
                  variant="outline"
                  size="sm"
                  icon="i-lucide-plus"
                  @click="addWebUrl"
                />
              </div>
            </div>
          </div>

          <!-- Right: File + URL list -->
          <div class="flex w-3/5 flex-col overflow-hidden rounded-lg border border-default">
            <!-- Header -->
            <div class="flex items-center justify-between border-b border-default px-3 py-2">
              <span class="text-xs text-muted-foreground">
                {{ t("knowledge.webItemsSelected", { selected: allSelectedCount, total: allItemsCount }) }}
              </span>
              <span class="text-xs text-muted-foreground">
                {{ t("knowledge.contentNamesMustBeUnique") }}
              </span>
            </div>

            <!-- Items -->
            <div class="flex-1 overflow-y-auto">
              <!-- Files -->
              <template v-if="fileItems.length">
                <div
                  v-for="(item, i) in fileItems"
                  :key="'f-' + i"
                  class="border-b border-default last:border-b-0"
                >
                  <div class="flex items-center gap-2 px-3 py-2.5">
                    <UCheckbox v-model="item.selected" />
                    <UIcon name="i-lucide-file" class="size-4 shrink-0 text-muted-foreground" />
                    <span class="min-w-0 flex-1 truncate text-sm">{{ item.file.name }}</span>
                    <UButton
                      color="neutral"
                      variant="ghost"
                      size="xs"
                      icon="i-lucide-trash-2"
                      @click="removeFileItem(i)"
                    />
                    <UButton
                      color="neutral"
                      variant="ghost"
                      size="xs"
                      :icon="item.expanded ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
                      @click="toggleFileItemExpand(i)"
                    />
                  </div>

                  <div v-if="item.expanded" class="space-y-3 border-t border-default px-3 py-3">
                    <div>
                      <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                        <UIcon name="i-lucide-type" class="size-4" />
                        {{ t("knowledge.name") }}
                      </label>
                      <UInput v-model="item.name" class="w-full" />
                    </div>

                    <div>
                      <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                        <UIcon name="i-lucide-align-left" class="size-4" />
                        {{ t("knowledge.descriptionOptional") }}
                      </label>
                      <UTextarea
                        v-model="item.description"
                        :placeholder="t('knowledge.descriptionPlaceholder')"
                        :rows="2"
                        class="w-full"
                      />
                    </div>

                    <div>
                      <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                        <UIcon name="i-lucide-settings-2" class="size-4" />
                        {{ t("knowledge.reader") }}
                      </label>
                      <div class="rounded-md bg-muted px-3 py-2 text-sm">
                        {{ readerItem.label }}
                      </div>
                    </div>

                    <div v-if="chunkerItems.length > 0">
                      <div class="flex items-center gap-2">
                        <USwitch v-model="item.chunkingEnabled" />
                        <span class="text-sm font-medium">{{ t("knowledge.configureChunking") }}</span>
                      </div>
                      <div
                        v-if="item.chunkingEnabled"
                        class="mt-2 space-y-2 rounded-md border border-default p-3"
                      >
                        <p class="text-xs text-muted-foreground">
                          {{ t("knowledge.chunkingHint") }}
                        </p>
                        <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                          <UIcon name="i-lucide-settings-2" class="size-4" />
                          {{ t("knowledge.chunker") }}
                        </label>
                        <USelectMenu
                          v-model="item.chunkerId"
                          value-key="id"
                          :items="chunkerItems"
                          :search-input="false"
                          class="w-full"
                        >
                          <template #item-trailing="{ item: chunkerItem }">
                            <UTooltip
                              v-if="chunkerItem._description"
                              :text="chunkerItem._description"
                            >
                              <UIcon
                                name="i-lucide-info"
                                class="size-4 cursor-help text-muted-foreground"
                              />
                            </UTooltip>
                          </template>
                        </USelectMenu>

                        <template v-if="chunkerHasSize(item.chunkerId)">
                          <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                            <UIcon name="i-lucide-settings-2" class="size-4" />
                            {{ t("knowledge.chunkSize") }}
                          </label>
                          <UInput
                            v-model.number="item.chunkSize"
                            type="number"
                            :min="100"
                            class="w-full"
                          />
                        </template>

                        <template v-if="chunkerHasOverlap(item.chunkerId)">
                          <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                            <UIcon name="i-lucide-settings-2" class="size-4" />
                            {{ t("knowledge.chunkOverlap") }}
                          </label>
                          <UInput
                            v-model.number="item.chunkOverlap"
                            type="number"
                            :min="0"
                            class="w-full"
                          />
                        </template>
                      </div>
                    </div>

                    <div>
                      <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                        <UIcon name="i-lucide-tags" class="size-4" />
                        {{ t("knowledge.metadataOptional") }}
                      </label>
                      <div class="flex items-center gap-2">
                        <UInput
                          v-model="item.metaKeyInput"
                          :placeholder="t('knowledge.metadataKey')"
                          class="flex-1"
                          @keydown.enter.prevent="addFileItemMeta(item)"
                        />
                        <span class="text-muted-foreground">=</span>
                        <UInput
                          v-model="item.metaValueInput"
                          :placeholder="t('knowledge.metadataValue')"
                          class="flex-1"
                          @keydown.enter.prevent="addFileItemMeta(item)"
                        />
                        <UButton
                          color="neutral"
                          variant="ghost"
                          size="sm"
                          icon="i-lucide-plus"
                          :disabled="!item.metaKeyInput.trim()"
                          @click="addFileItemMeta(item)"
                        />
                      </div>
                      <div v-if="item.metadata.length" class="mt-2 flex flex-wrap gap-1.5">
                        <UBadge
                          v-for="(row, mi) in item.metadata"
                          :key="mi"
                          color="neutral"
                          variant="subtle"
                          size="md"
                          class="gap-1 pl-2 pr-1"
                        >
                          {{ row.key }} = {{ row.value }}
                          <UButton
                            color="neutral"
                            variant="link"
                            size="xs"
                            icon="i-lucide-x"
                            class="ml-0.5 size-4"
                            @click="removeFileItemMeta(item, mi)"
                          />
                        </UBadge>
                      </div>
                    </div>
                  </div>
                </div>
              </template>

              <!-- Web URLs -->
              <template v-if="webItems.length">
                <div
                  v-for="(item, i) in webItems"
                  :key="'w-' + i"
                  class="border-b border-default last:border-b-0"
                >
                  <div class="flex items-center gap-2 px-3 py-2.5">
                    <UCheckbox v-model="item.selected" />
                    <UIcon name="i-lucide-globe" class="size-4 shrink-0 text-muted-foreground" />
                    <span class="min-w-0 flex-1 truncate text-sm">{{ item.url }}</span>
                    <UButton
                      color="neutral"
                      variant="ghost"
                      size="xs"
                      icon="i-lucide-trash-2"
                      @click="removeWebItem(i)"
                    />
                    <UButton
                      color="neutral"
                      variant="ghost"
                      size="xs"
                      :icon="item.expanded ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
                      @click="toggleWebItemExpand(i)"
                    />
                  </div>

                  <div v-if="item.expanded" class="space-y-3 border-t border-default px-3 py-3">
                    <div>
                      <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                        <UIcon name="i-lucide-type" class="size-4" />
                        {{ t("knowledge.name") }}
                      </label>
                      <UInput v-model="item.name" class="w-full" />
                    </div>

                    <div>
                      <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                        <UIcon name="i-lucide-align-left" class="size-4" />
                        {{ t("knowledge.descriptionOptional") }}
                      </label>
                      <UTextarea
                        v-model="item.description"
                        :placeholder="t('knowledge.descriptionPlaceholder')"
                        :rows="2"
                        class="w-full"
                      />
                    </div>

                    <div>
                      <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                        <UIcon name="i-lucide-settings-2" class="size-4" />
                        {{ t("knowledge.reader") }}
                      </label>
                      <div class="rounded-md bg-muted px-3 py-2 text-sm">
                        {{ readerItem.label }}
                      </div>
                    </div>

                    <div v-if="chunkerItems.length > 0">
                      <div class="flex items-center gap-2">
                        <USwitch v-model="item.chunkingEnabled" />
                        <span class="text-sm font-medium">{{ t("knowledge.configureChunking") }}</span>
                      </div>
                      <div
                        v-if="item.chunkingEnabled"
                        class="mt-2 space-y-2 rounded-md border border-default p-3"
                      >
                        <p class="text-xs text-muted-foreground">
                          {{ t("knowledge.chunkingHint") }}
                        </p>
                        <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                          <UIcon name="i-lucide-settings-2" class="size-4" />
                          {{ t("knowledge.chunker") }}
                        </label>
                        <USelectMenu
                          v-model="item.chunkerId"
                          value-key="id"
                          :items="chunkerItems"
                          :search-input="false"
                          class="w-full"
                        >
                          <template #item-trailing="{ item: chunkerItem }">
                            <UTooltip
                              v-if="chunkerItem._description"
                              :text="chunkerItem._description"
                            >
                              <UIcon
                                name="i-lucide-info"
                                class="size-4 cursor-help text-muted-foreground"
                              />
                            </UTooltip>
                          </template>
                        </USelectMenu>

                        <template v-if="chunkerHasSize(item.chunkerId)">
                          <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                            <UIcon name="i-lucide-settings-2" class="size-4" />
                            {{ t("knowledge.chunkSize") }}
                          </label>
                          <UInput
                            v-model.number="item.chunkSize"
                            type="number"
                            :min="100"
                            class="w-full"
                          />
                        </template>

                        <template v-if="chunkerHasOverlap(item.chunkerId)">
                          <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                            <UIcon name="i-lucide-settings-2" class="size-4" />
                            {{ t("knowledge.chunkOverlap") }}
                          </label>
                          <UInput
                            v-model.number="item.chunkOverlap"
                            type="number"
                            :min="0"
                            class="w-full"
                          />
                        </template>
                      </div>
                    </div>

                    <div>
                      <label class="mb-1 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                        <UIcon name="i-lucide-tags" class="size-4" />
                        {{ t("knowledge.metadataOptional") }}
                      </label>
                      <div class="flex items-center gap-2">
                        <UInput
                          v-model="item.metaKeyInput"
                          :placeholder="t('knowledge.metadataKey')"
                          class="flex-1"
                          @keydown.enter.prevent="addWebItemMeta(item)"
                        />
                        <span class="text-muted-foreground">=</span>
                        <UInput
                          v-model="item.metaValueInput"
                          :placeholder="t('knowledge.metadataValue')"
                          class="flex-1"
                          @keydown.enter.prevent="addWebItemMeta(item)"
                        />
                        <UButton
                          color="neutral"
                          variant="ghost"
                          size="sm"
                          icon="i-lucide-plus"
                          :disabled="!item.metaKeyInput.trim()"
                          @click="addWebItemMeta(item)"
                        />
                      </div>
                      <div v-if="item.metadata.length" class="mt-2 flex flex-wrap gap-1.5">
                        <UBadge
                          v-for="(row, mi) in item.metadata"
                          :key="mi"
                          color="neutral"
                          variant="subtle"
                          size="md"
                          class="gap-1 pl-2 pr-1"
                        >
                          {{ row.key }} = {{ row.value }}
                          <UButton
                            color="neutral"
                            variant="link"
                            size="xs"
                            icon="i-lucide-x"
                            class="ml-0.5 size-4"
                            @click="removeWebItemMeta(item, mi)"
                          />
                        </UBadge>
                      </div>
                    </div>
                  </div>
                </div>
              </template>

              <!-- Empty state -->
              <div
                v-if="!fileItems.length && !webItems.length"
                class="flex min-h-30 items-center justify-center text-sm text-muted-foreground"
              >
                {{ t("knowledge.noFilesYet") }}
              </div>
            </div>
          </div>
        </div>
      </template>

      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            color="neutral"
            variant="outline"
            @click="addDialogOpen = false"
          >
            {{ t("common.cancel") }}
          </UButton>
          <UButton
            color="primary"
            variant="solid"
            :loading="uploadingFile"
            :disabled="!fileItems.length && !webItems.length"
            @click="submitAll()"
          >
            {{ t('knowledge.save') }}
          </UButton>
        </div>
      </template>
    </UModal>
  </div>
</template>
