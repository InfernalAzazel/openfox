import { agentOsRequest, readAgentOsErrorMessage } from '@/composables/request'
import { APIRoutes } from './routes'

export interface UserMemory {
  memory_id: string
  memory: string
  topics?: string[] | null
  agent_id?: string | null
  team_id?: string | null
  user_id?: string | null
  updated_at?: string | null
}

export interface UserMemoryCreate {
  memory: string
  user_id?: string | null
  topics?: string[] | null
}

export interface UserStats {
  user_id: string
  total_memories: number
  last_memory_updated_at?: string | null
}

export interface PaginationInfo {
  page: number
  limit: number
  total_pages: number
  total_count: number
  search_time_ms: number
}

export interface PaginatedResponse<T> {
  data: T[]
  meta: PaginationInfo
}

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; message: string }

export type ApiVoidResult =
  | { ok: true }
  | { ok: false; status: number; message: string }

export async function getUserMemoryStatsAPI(
  base: string,
  authToken: string | undefined,
  params: { limit?: number; page?: number; user_id?: string } = {},
): Promise<ApiResult<PaginatedResponse<UserStats>>> {
  const sp = new URLSearchParams()
  if (params.limit != null) sp.set('limit', String(params.limit))
  if (params.page != null) sp.set('page', String(params.page))
  if (params.user_id?.trim()) sp.set('user_id', params.user_id.trim())
  const q = sp.toString()
  const path = APIRoutes.GetUserMemoryStats(base)
  const href = q ? `${path}?${q}` : path
  try {
    const res = await agentOsRequest(href, { method: 'GET', authToken })
    if (!res.ok) {
      const message = await readAgentOsErrorMessage(res)
      return { ok: false, status: res.status, message }
    }
    const data = (await res.json()) as PaginatedResponse<UserStats>
    return { ok: true, data }
  } catch (e) {
    return { ok: false, status: 0, message: e instanceof Error ? e.message : 'Network error' }
  }
}

export async function listMemoriesAPI(
  base: string,
  authToken: string | undefined,
  params: {
    user_id?: string
    limit?: number
    page?: number
    sort_by?: string
    sort_order?: 'asc' | 'desc'
  } = {},
): Promise<ApiResult<PaginatedResponse<UserMemory>>> {
  const sp = new URLSearchParams()
  if (params.user_id?.trim()) sp.set('user_id', params.user_id.trim())
  if (params.limit != null) sp.set('limit', String(params.limit))
  if (params.page != null) sp.set('page', String(params.page))
  if (params.sort_by) sp.set('sort_by', params.sort_by)
  if (params.sort_order) sp.set('sort_order', params.sort_order)
  const q = sp.toString()
  const path = APIRoutes.ListMemories(base)
  const href = q ? `${path}?${q}` : path
  try {
    const res = await agentOsRequest(href, { method: 'GET', authToken })
    if (!res.ok) {
      const message = await readAgentOsErrorMessage(res)
      return { ok: false, status: res.status, message }
    }
    const data = (await res.json()) as PaginatedResponse<UserMemory>
    return { ok: true, data }
  } catch (e) {
    return { ok: false, status: 0, message: e instanceof Error ? e.message : 'Network error' }
  }
}

export async function createMemoryAPI(
  base: string,
  authToken: string | undefined,
  body: UserMemoryCreate,
): Promise<ApiResult<UserMemory>> {
  try {
    const res = await agentOsRequest(APIRoutes.CreateMemory(base), {
      method: 'POST',
      authToken,
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const message = await readAgentOsErrorMessage(res)
      return { ok: false, status: res.status, message }
    }
    const data = (await res.json()) as UserMemory
    return { ok: true, data }
  } catch (e) {
    return { ok: false, status: 0, message: e instanceof Error ? e.message : 'Network error' }
  }
}

export async function updateMemoryAPI(
  base: string,
  authToken: string | undefined,
  memoryId: string,
  body: UserMemoryCreate,
): Promise<ApiResult<UserMemory>> {
  try {
    const res = await agentOsRequest(APIRoutes.UpdateMemory(base, memoryId), {
      method: 'PATCH',
      authToken,
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const message = await readAgentOsErrorMessage(res)
      return { ok: false, status: res.status, message }
    }
    const data = (await res.json()) as UserMemory
    return { ok: true, data }
  } catch (e) {
    return { ok: false, status: 0, message: e instanceof Error ? e.message : 'Network error' }
  }
}

export async function deleteMemoriesBatchAPI(
  base: string,
  authToken: string | undefined,
  memoryIds: string[],
  userId?: string,
): Promise<ApiVoidResult> {
  try {
    const res = await agentOsRequest(APIRoutes.DeleteMemories(base), {
      method: 'DELETE',
      authToken,
      body: JSON.stringify({
        memory_ids: memoryIds,
        ...(userId?.trim() ? { user_id: userId.trim() } : {}),
      }),
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

export async function deleteMemoryAPI(
  base: string,
  authToken: string | undefined,
  memoryId: string,
  userId?: string,
): Promise<ApiVoidResult> {
  const sp = new URLSearchParams()
  if (userId?.trim()) sp.set('user_id', userId.trim())
  const q = sp.toString()
  const path = APIRoutes.DeleteMemory(base, memoryId)
  const href = q ? `${path}?${q}` : path
  try {
    const res = await agentOsRequest(href, { method: 'DELETE', authToken })
    if (!res.ok) {
      const message = await readAgentOsErrorMessage(res)
      return { ok: false, status: res.status, message }
    }
    return { ok: true }
  } catch (e) {
    return { ok: false, status: 0, message: e instanceof Error ? e.message : 'Network error' }
  }
}
