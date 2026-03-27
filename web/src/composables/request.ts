import { createFetch } from '@vueuse/core'
import { useAppState } from '@/composables/store'

/** 与 `vite.config.ts` 中 `server.proxy` 前缀一致 */
export const AGENT_OS_PROXY_PREFIX = '/agent-os'

function stripTrailingSlash(s: string): string {
  return s.replace(/\/$/, '')
}

/**
 * 开发模式下若配置为 `localhost` / `127.0.0.1:7777`，改为走 Vite 代理前缀，避免跨域与 OPTIONS 预检失败。
 */
function devProxyBaseIfLocalAgentOs(base: string): string {
  if (!import.meta.env.DEV) return base
  if (!base.startsWith('http')) return base
  try {
    const u = new URL(base)
    const port = u.port || (u.protocol === 'https:' ? '443' : '80')
    if (
      port === '7777' &&
      (u.hostname === 'localhost' || u.hostname === '127.0.0.1')
    ) {
      return AGENT_OS_PROXY_PREFIX
    }
  } catch {
    /* ignore */
  }
  return base
}

/**
 * Agent OS 根地址：优先登录页保存的 `os_base_url`，否则用 `VITE_OS_API_BASE`。
 * 开发环境 + 本机 7777 时会转为 `/agent-os`（经 Vite 转发到真实 OS）。
 */
export function getAgentOsBaseUrl(): string {
  const saved = useAppState().value.os_base_url?.trim()
  const raw = saved
    ? stripTrailingSlash(saved)
    : typeof import.meta.env.VITE_OS_API_BASE === 'string'
      ? stripTrailingSlash(import.meta.env.VITE_OS_API_BASE.trim())
      : ''
  if (!raw) return ''
  return devProxyBaseIfLocalAgentOs(raw)
}

/**
 * 登录/配置里保存的「原始」基础 URL（不做开发代理改写），用于展示或需直连的场景。
 */
export function getStoredAgentOsBaseUrl(): string {
  const saved = useAppState().value.os_base_url?.trim()
  if (saved) return stripTrailingSlash(saved)
  const base = import.meta.env.VITE_OS_API_BASE
  return typeof base === 'string' ? stripTrailingSlash(base.trim()) : ''
}

/** 与 [agent-ui createHeaders](https://github.com/agno-agi/agent-ui/blob/main/src/api/os.ts) 一致 */
export function createAgentOsHeaders(authToken?: string): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`
  }
  return headers
}

/**
 * VueUse 预配置的 `useFetch`，适合在 `setup()` 里做响应式请求。
 *
 * @example
 * ```ts
 * const { data, error, execute, isFetching } = useAgentOsFetch('/agents')
 *   .get()
 *   .json<AgentDetails[]>()
 * ```
 */
export const useAgentOsFetch = createFetch({
  baseUrl: getAgentOsBaseUrl,
  combination: 'chain',
  options: {
    beforeFetch({ options }) {
      const h = new Headers(options.headers as HeadersInit)
      if (!h.has('Content-Type')) {
        h.set('Content-Type', 'application/json')
      }
      options.headers = h
      return { options }
    },
  },
})

export type AgentOsRequestInit = RequestInit & { authToken?: string }

/**
 * 命令式请求（服务函数、非 Vue 上下文），与 `useAgentOsFetch` 使用相同的 baseUrl 与默认头。
 * `path` 相对于 `VITE_OS_API_BASE`；已是 `http(s)://` 的地址则原样使用。
 */
export async function agentOsRequest(
  path: string,
  init: AgentOsRequestInit = {},
): Promise<Response> {
  const base = getAgentOsBaseUrl()
  const { authToken, headers: initHeaders, ...rest } = init
  let url: string
  if (path.startsWith('http://') || path.startsWith('https://')) {
    url = path
  } else if (path.startsWith('/')) {
    // `APIRoutes.*` 已包含完整根路径（如 `/agent-os/agents`），勿再拼 `base`
    url = path
  } else {
    const b = stripTrailingSlash(base)
    url = b ? `${b}/${path}` : `/${path}`
  }

  const headers = new Headers(createAgentOsHeaders(authToken))
  if (initHeaders) {
    new Headers(initHeaders as HeadersInit).forEach((value, key) => {
      headers.set(key, value)
    })
  }

  if (rest.body instanceof FormData)
    headers.delete('Content-Type')

  return fetch(url, {
    ...rest,
    headers,
  })
}

/**
 * 从 Agent OS 失败响应中解析可读说明（常见：FastAPI `detail`、通用 `message`、或原始文本）。
 */
export async function readAgentOsErrorMessage(res: Response): Promise<string> {
  const status = res.status
  let body = ''
  try {
    body = await res.text()
  } catch {
    return `请求失败（HTTP ${status}）`
  }
  const trimmed = body.trim()
  if (!trimmed) {
    return `请求失败（HTTP ${status}）`
  }
  try {
    const j = JSON.parse(trimmed) as Record<string, unknown>
    const detail = j.detail
    if (typeof detail === 'string') {
      return detail
    }
    if (Array.isArray(detail)) {
      const parts = detail.map((item) => {
        if (item && typeof item === 'object' && item !== null && 'msg' in item) {
          return String((item as { msg?: unknown }).msg ?? JSON.stringify(item))
        }
        return String(item)
      })
      const s = parts.filter(Boolean).join('；')
      if (s) {
        return s
      }
    }
    if (typeof j.message === 'string') {
      return j.message
    }
  } catch {
    /* 非 JSON */
  }
  return trimmed.length > 480 ? `${trimmed.slice(0, 480)}…` : trimmed
}
