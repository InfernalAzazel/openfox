import { useAppState } from '@/composables/store'
import { createRouter, createWebHistory } from 'vue-router'
import { routes } from 'vue-router/auto-routes'
import { setupLayouts } from 'virtual:generated-layouts'

function safeRedirectPath(raw: unknown): string {
  if (typeof raw !== 'string' || !raw.startsWith('/') || raw.startsWith('//')) {
    return '/'
  }
  return raw
}

export const router = createRouter({
  /** 与 `vite.config` 的 `base` 一致；挂载在子路径（如 FastAPI `/app`）时必设 */
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: setupLayouts(routes),
})

router.beforeEach((to) => {
  const state = useAppState()
  const authed = Boolean(state.value.access_token?.trim())

  if (to.path === '/login') {
    if (authed) {
      return safeRedirectPath(to.query.redirect)
    }
    return true
  }

  const requiresAuth = to.meta.requiresAuth ?? true
  if (requiresAuth && !authed) {
    return {
      path: '/login',
      query: { redirect: to.fullPath },
    }
  }

  return true
})
