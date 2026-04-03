<script setup lang="ts" generic="TData">
import type { ColumnDef, Row } from "@tanstack/vue-table"
import {
  FlexRender,
  getCoreRowModel,
  useVueTable,
} from "@tanstack/vue-table"
import { computed, useSlots } from "vue"

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"

const props = withDefaults(
  defineProps<{
    /** 各列 TValue 不一致时用 any 避免与 createColumnHelper 推导冲突 */
    columns: ColumnDef<TData, any>[]
    data: TData[]
    /** 额外 class 传给 `<Table>` */
    tableClass?: string
    /** 表头 `<TableRow>` */
    headerRowClass?: string
    /** 表体 `<TableRow>` */
    bodyRowClass?: string
    getRowId?: (originalRow: TData, index: number) => string
    /** `<TableHead>` class，签名为 (columnId) => string */
    headerClass?: (columnId: string) => string
    /** `<TableCell>` class */
    cellClass?: (columnId: string) => string
    /** 首屏加载且无数据时展示一行占位 */
    loading?: boolean
    loadingLabel?: string
    /** 非加载且无数据 */
    emptyLabel?: string
  }>(),
  {
    tableClass: "",
    headerRowClass: "border-border hover:bg-transparent",
    bodyRowClass:
      "border-border/80 transition-colors hover:bg-muted/50 dark:hover:bg-white/5",
    loading: false,
    loadingLabel: "",
    emptyLabel: "",
  },
)

const slots = useSlots()

const table = useVueTable({
  get data() {
    return props.data
  },
  get columns() {
    return props.columns
  },
  getCoreRowModel: getCoreRowModel(),
  getRowId: props.getRowId
    ? (originalRow, i) => props.getRowId!(originalRow as TData, i)
    : undefined,
})

const colspan = computed(() => props.columns.length)

function slotName(columnId: string) {
  return `cell-${columnId}` as keyof typeof slots
}

function hasCellSlot(columnId: string) {
  return Boolean(slots[slotName(columnId)])
}

defineExpose({ table })
</script>

<template>
  <Table :class="cn(props.tableClass)">
    <TableHeader>
      <TableRow
        v-for="headerGroup in table.getHeaderGroups()"
        :key="headerGroup.id"
        :class="headerRowClass"
      >
        <TableHead
          v-for="header in headerGroup.headers"
          :key="header.id"
          :class="headerClass?.(header.column.id)"
        >
          <FlexRender
            v-if="!header.isPlaceholder"
            :render="header.column.columnDef.header"
            :props="header.getContext()"
          />
        </TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      <template v-if="loading && !data.length">
        <TableRow>
          <TableCell :colspan="colspan" class="py-8 text-center">
            <span class="text-sm text-muted-foreground">{{ loadingLabel }}</span>
          </TableCell>
        </TableRow>
      </template>
      <template v-else-if="!table.getRowModel().rows.length">
        <TableRow>
          <TableCell :colspan="colspan" class="py-8 text-center">
            <span class="text-sm text-muted-foreground">{{ emptyLabel }}</span>
          </TableCell>
        </TableRow>
      </template>
      <template v-else>
        <TableRow
          v-for="row in table.getRowModel().rows"
          :key="row.id"
          :class="bodyRowClass"
        >
          <TableCell
            v-for="cell in row.getVisibleCells()"
            :key="cell.id"
            :class="cellClass?.(cell.column.id)"
          >
            <slot
              v-if="hasCellSlot(cell.column.id)"
              :name="slotName(cell.column.id)"
              v-bind="{
                row: row as Row<TData>,
                cell,
                original: row.original as TData,
              }"
            />
            <FlexRender
              v-else-if="cell.column.columnDef.cell"
              :render="cell.column.columnDef.cell"
              :props="cell.getContext()"
            />
          </TableCell>
        </TableRow>
      </template>
    </TableBody>
  </Table>
</template>
