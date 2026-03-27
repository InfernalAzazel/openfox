import 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    /** 需要 `useAppState().access_token`，未登录会跳转 `/login` */
    requiresAuth?: boolean
    /**
     * vite-plugin-vue-layouts：`layouts` 目录下组件名（不含 `.vue`），或 `false` 表示不套布局。
     * @see https://github.com/JohnCampionJr/vite-plugin-vue-layouts
     */
    layout?: string | false
    /** 由 vite-plugin-vue-layouts 注入，用于识别布局包装路由 */
    isLayout?: boolean
  }
}

export {}
