<script setup lang="ts">
defineProps<{
  /** 合并到主内容区，用于单页收紧左右留白，如 `px-3 md:px-4` */
  contentClass?: string
}>()
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col bg-background">
    <div :class="['flex-1 overflow-auto p-6 text-foreground', contentClass]">
      <slot />
    </div>
  </div>
</template>
