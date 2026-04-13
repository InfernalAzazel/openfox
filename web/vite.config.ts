import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'
import VueRouter from 'vue-router/vite'
import VueI18nPlugin from '@intlify/unplugin-vue-i18n/vite'
import Layouts from 'vite-plugin-vue-layouts'
import { fileURLToPath } from 'node:url'
import ui from '@nuxt/ui/vite'

const projectRoot = path.dirname(fileURLToPath(import.meta.url))

/** 在 Node 解析 package exports 之前拦截，避免 ./vue-plugin 仅有 types、无 import 时报错 */
function nuxtUiVuePluginResolve(): Plugin {
  return {
    name: 'nuxt-ui-vue-plugin-resolve',
    enforce: 'pre',
    resolveId(id) {
      if (id === '@nuxt/ui/vue-plugin') {
        return 'virtual:nuxt-ui-plugins'
      }
    },
  }
}

/** FastAPI 子路径挂载时设置 `VITE_APP_BASE=/prefix`（自动补尾斜杠） */
function viteAppBase(): string {
  const raw = process.env.VITE_APP_BASE?.trim()
  if (!raw || raw === '/') {
    return '/'
  }
  return raw.endsWith('/') ? raw : `${raw}/`
}

// https://vite.dev/config/
export default defineConfig({
  base: viteAppBase(),
  plugins: [
    VueRouter(),
    vue(),
    Layouts(),
    tailwindcss(),
    nuxtUiVuePluginResolve(),
    ui(),
    VueI18nPlugin({
      include: path.resolve(projectRoot, 'src/i18n/locales/**'),
      runtimeOnly: false,
      compositionOnly: true,
      fullInstall: true
    })
  ],
  resolve: {
    alias: {
      '@': path.resolve(projectRoot, './src'),
      '@i18n': fileURLToPath(new URL('./src/i18n', import.meta.url)),
    },
  },
  server: {
    proxy: {
      // 开发与 Agent OS 不同源时，用同源路径 + 代理避免 CORS（OPTIONS 预检）失败
      '/agent-os': {
        target: process.env.VITE_AGENT_OS_PROXY_TARGET || 'http://127.0.0.1:7777',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/agent-os/, '') || '/',
      },
    },
  },
})
