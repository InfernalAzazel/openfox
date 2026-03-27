<script setup lang="ts">
/**
 * 根组件仅挂载顶层 `<RouterView />`，由路由树决定呈现页面或嵌套布局。
 * @see https://router.vuejs.org/guide/essentials/nested-routes.html
 */
import { RouterView } from "vue-router"
</script>

<template>
  <RouterView />
</template>
