import { agentOsRequest, readAgentOsErrorMessage } from '@/composables/request'
import { APIRoutes } from './routes'
import type { PaginatedResponse, ApiResult, ApiVoidResult } from './memory'

export type ContentStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface KnowledgeContent {
  id: string
  name?: string | null
  description?: string | null
  type?: string | null
  size?: string | null
  linked_to?: string | null
  metadata?: Record<string, unknown> | null
  access_count?: number | null
  status?: ContentStatus | null
  status_message?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface KnowledgeConfig {
  readers?: Record<string, { id: string; name?: string; description?: string }> | null
  readersForType?: Record<string, string[]> | null
  chunkers?: Record<string, { id: string; name?: string; description?: string }> | null
  filters?: string[] | null
}

export async function listContentAPI(
  base: string,
  authToken: string | undefined,
  params: { limit?: number; page?: number; sort_by?: string; sort_order?: string } = {},
): Promise<ApiResult<PaginatedResponse<KnowledgeContent>>> {
  const sp = new URLSearchParams()
  if (params.limit != null) sp.set('limit', String(params.limit))
  if (params.page != null) sp.set('page', String(params.page))
  if (params.sort_by) sp.set('sort_by', params.sort_by)
  if (params.sort_order) sp.set('sort_order', params.sort_order)
  const q = sp.toString()
  const path = APIRoutes.KnowledgeContent(base)
  const href = q ? `${path}?${q}` : path
  try {
    const res = await agentOsRequest(href, { method: 'GET', authToken })
    if (!res.ok) {
      const message = await readAgentOsErrorMessage(res)
      return { ok: false, status: res.status, message }
    }
    const data = await res.json()
    return { ok: true, data }
  } catch (e) {
    return { ok: false, status: 0, message: e instanceof Error ? e.message : 'Network error' }
  }
}

export async function getConfigAPI(
  base: string,
  authToken: string | undefined,
): Promise<ApiResult<KnowledgeConfig>> {
  try {
    const res = await agentOsRequest(APIRoutes.KnowledgeConfig(base), { method: 'GET', authToken })
    if (!res.ok) {
      const message = await readAgentOsErrorMessage(res)
      return { ok: false, status: res.status, message }
    }
    const data = await res.json()
    return { ok: true, data }
  } catch (e) {
    return { ok: false, status: 0, message: e instanceof Error ? e.message : 'Network error' }
  }
}

export async function uploadContentAPI(
  base: string,
  authToken: string | undefined,
  formData: FormData,
): Promise<ApiResult<KnowledgeContent>> {
  try {
    const res = await agentOsRequest(APIRoutes.KnowledgeContent(base), {
      method: 'POST',
      authToken,
      body: formData,
    })
    if (!res.ok) {
      const message = await readAgentOsErrorMessage(res)
      return { ok: false, status: res.status, message }
    }
    const data = await res.json()
    return { ok: true, data }
  } catch (e) {
    return { ok: false, status: 0, message: e instanceof Error ? e.message : 'Network error' }
  }
}

export async function updateContentAPI(
  base: string,
  authToken: string | undefined,
  contentId: string,
  body: { name?: string; description?: string; metadata?: string },
): Promise<ApiResult<KnowledgeContent>> {
  const formBody = new URLSearchParams()
  if (body.name != null) formBody.set('name', body.name)
  if (body.description != null) formBody.set('description', body.description)
  if (body.metadata != null) formBody.set('metadata', body.metadata)
  try {
    const res = await agentOsRequest(APIRoutes.KnowledgeContentById(base, contentId), {
      method: 'PATCH',
      authToken,
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formBody.toString(),
    })
    if (!res.ok) {
      const message = await readAgentOsErrorMessage(res)
      return { ok: false, status: res.status, message }
    }
    const data = await res.json()
    return { ok: true, data }
  } catch (e) {
    return { ok: false, status: 0, message: e instanceof Error ? e.message : 'Network error' }
  }
}

export async function deleteContentAPI(
  base: string,
  authToken: string | undefined,
  contentId: string,
): Promise<ApiVoidResult> {
  try {
    const res = await agentOsRequest(APIRoutes.KnowledgeContentById(base, contentId), {
      method: 'DELETE',
      authToken,
    })
    if (!res.ok) {
      const message = await readAgentOsErrorMessage(res)
      return { ok: false, status: res.status, message }
    }
    return { ok: true }
  } catch (e) {
    return { ok: false, status: 0, message: e instanceof Error ? e.message : 'Network error' }
  }
}
