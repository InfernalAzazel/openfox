<script setup lang="ts">
import type { HTMLAttributes } from "vue"
import { PanelLeft, PanelRight } from "lucide-vue-next"
import { computed } from "vue"
import { cn } from "@/lib/utils"
import { Button } from '@/components/ui/button'
import { useSidebar } from "./utils"

const props = defineProps<{
  class?: HTMLAttributes["class"]
}>()

const { toggleSidebar, state, isMobile } = useSidebar()

/** 移动端：左侧抽屉仍用 PanelLeft；桌面端收缩时用 PanelRight 表示「展开侧栏」 */
const TriggerIcon = computed(() =>
  isMobile.value ? PanelLeft : state.value === "collapsed" ? PanelRight : PanelLeft,
)
</script>

<template>
  <Button
    data-sidebar="trigger"
    data-slot="sidebar-trigger"
    variant="ghost"
    size="icon"
    :class="cn('h-7 w-7', props.class)"
    @click="toggleSidebar"
  >
    <component :is="TriggerIcon" class="size-4" />
    <span class="sr-only">Toggle Sidebar</span>
  </Button>
</template>
