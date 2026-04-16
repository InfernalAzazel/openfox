/**
 * Agent OS HTTP（与 agent-ui 官方 `api/os.ts` 对齐）+ OpenFox `/config`、`/skills`。
 * @see https://github.com/agno-agi/agent-ui/blob/main/src/api/os.ts
 */
import {
  agentOsRequest,
  createAgentOsHeaders,
  readAgentOsErrorMessage,
} from '@/composables/request'
import type {
  AgentDetails,
  AgentOsDayAggregatedMetrics,
  AgentOsMetricsResponse,
  SessionEntry,
  Sessions,
  TeamDetails,
} from '@/types/os'
import { APIRoutes } from './routes'

/** 会话列表拉取结果（失败时携带可读 `message`，供界面红字展示） */
export type GetAllSessionsAPIResult =
  | { ok: true; data: SessionEntry[] }
  | { ok: false; message: string }

/** 与 agent-ui `createHeaders` 一致；实现复用 `createAgentOsHeaders` */
export function createHeaders(authToken?: string): HeadersInit {
  return createAgentOsHeaders(authToken)
}

export const getAgentsAPI = async (
  endpoint: string,
  authToken?: string,
): Promise<AgentDetails[]> => {
  const url = APIRoutes.GetAgents(endpoint)
  try {
    const response = await agentOsRequest(url, {
      method: 'GET',
      authToken,
    })
    if (!response.ok) {
      return []
    }
    const data: unknown = await response.json()
    return data as AgentDetails[]
  } catch {
    return []
  }
}

export const getStatusAPI = async (
  base: string,
  authToken?: string,
): Promise<number> => {
  const response = await agentOsRequest(APIRoutes.Status(base), {
    method: 'GET',
    authToken,
  })
  return response.status
}

export const getAllSessionsAPI = async (
  base: string,
  type: 'agent' | 'team',
  componentId: string,
  dbId: string,
  authToken?: string,
): Promise<GetAllSessionsAPIResult> => {
  try {
    const path = APIRoutes.GetSessions(base)
    const sp = new URLSearchParams()
    sp.set('type', type)
    sp.set('component_id', componentId)
    if (dbId.trim()) {
      sp.set('db_id', dbId)
    }
    const qs = sp.toString()
    const href = `${path}${path.includes('?') ? '&' : '?'}${qs}`

    const response = await agentOsRequest(href, {
      method: 'GET',
      authToken,
    })

    if (!response.ok) {
      if (response.status === 404) {
        return { ok: true, data: [] }
      }
      const message = await readAgentOsErrorMessage(response)
      return { ok: false, message }
    }
    const parsed = (await response.json()) as Sessions
    const data = Array.isArray(parsed.data) ? parsed.data : []
    return { ok: true, data }
  } catch (e) {
    const message =
      e instanceof Error && e.message.trim()
        ? e.message
        : 'Network error'
    return { ok: false, message }
  }
}

export const getSessionAPI = async (
  base: string,
  type: 'agent' | 'team',
  sessionId: string,
  dbId?: string,
  authToken?: string,
) => {
  const queryParams = new URLSearchParams({ type })
  if (dbId?.trim()) queryParams.append('db_id', dbId)

  const response = await agentOsRequest(
    `${APIRoutes.GetSession(base, sessionId)}?${queryParams.toString()}`,
    {
      method: 'GET',
      authToken,
    },
  )

  if (!response.ok) {
    throw new Error(`Failed to fetch session: ${response.statusText}`)
  }

  return response.json()
}

export const deleteSessionAPI = async (
  base: string,
  dbId: string,
  sessionId: string,
  authToken?: string,
) => {
  const queryParams = new URLSearchParams()
  if (dbId) queryParams.append('db_id', dbId)
  const q = queryParams.toString()
  const path = `${APIRoutes.DeleteSession(base, sessionId)}${q ? `?${q}` : ''}`
  const response = await agentOsRequest(path, {
    method: 'DELETE',
    authToken,
  })
  return response
}

export const getTeamsAPI = async (
  endpoint: string,
  authToken?: string,
): Promise<TeamDetails[]> => {
  const url = APIRoutes.GetTeams(endpoint)
  try {
    const response = await agentOsRequest(url, {
      method: 'GET',
      authToken,
    })
    if (!response.ok) {
      return []
    }
    const data: unknown = await response.json()
    return data as TeamDetails[]
  } catch {
    return []
  }
}

export const deleteTeamSessionAPI = async (
  base: string,
  teamId: string,
  sessionId: string,
  authToken?: string,
) => {
  const response = await agentOsRequest(
    APIRoutes.DeleteTeamSession(base, teamId, sessionId),
    {
      method: 'DELETE',
      authToken,
    },
  )

  if (!response.ok) {
    throw new Error(`Failed to delete team session: ${response.statusText}`)
  }
  return response
}

/** POST `/agents/{agent_id}/runs`（`application/x-www-form-urlencoded`） */
export type RunAgentPayload = {
  message: string
  stream?: boolean
  sessionId?: string
  userId?: string
}

export async function runAgentAPI(
  base: string,
  agentId: string,
  payload: RunAgentPayload,
  authToken?: string,
): Promise<unknown> {
  const url = APIRoutes.AgentRun(base, agentId)

  const response = await agentOsRequest(url, {
    method: 'POST',
    authToken,
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: (() => {
      const body = new URLSearchParams()
      body.set('message', payload.message)
      body.set('stream', String(payload.stream ?? false))
      if (payload.sessionId) body.set('session_id', payload.sessionId)
      if (payload.userId) body.set('user_id', payload.userId)
      return body.toString()
    })(),
  })

  if (!response.ok) {
    const errText = await response.text()
    throw new Error(errText || `${response.status} ${response.statusText}`)
  }

  const ct = response.headers.get('content-type') ?? ''
  if (ct.includes('application/json')) {
    return response.json()
  }
  return response.text()
}

/** `GET /metrics` 查询参数 @see OpenAPI get_metrics */
export type GetMetricsParams = {
  starting_date?: string
  ending_date?: string
  db_id?: string
  table?: string
}

export async function getMetricsAPI(
  base: string,
  authToken: string | undefined,
  params: GetMetricsParams = {},
): Promise<AgentOsMetricsResponse | null> {
  const sp = new URLSearchParams()
  if (params.starting_date) sp.set('starting_date', params.starting_date)
  if (params.ending_date) sp.set('ending_date', params.ending_date)
  if (params.db_id?.trim()) sp.set('db_id', params.db_id.trim())
  if (params.table?.trim()) sp.set('table', params.table.trim())
  const q = sp.toString()
  const path = APIRoutes.GetMetrics(base)
  const href = q ? `${path}?${q}` : path
  try {
    const response = await agentOsRequest(href, {
      method: 'GET',
      authToken,
    })
    if (!response.ok) {
      return null
    }
    const data: unknown = await response.json()
    return data as AgentOsMetricsResponse
  } catch {
    return null
  }
}

/** `POST /metrics/refresh` @see OpenAPI refresh_metrics */
export type RefreshMetricsParams = {
  db_id?: string
  table?: string
}

export async function refreshMetricsAPI(
  base: string,
  authToken: string | undefined,
  params: RefreshMetricsParams = {},
): Promise<AgentOsDayAggregatedMetrics[] | null> {
  const sp = new URLSearchParams()
  if (params.db_id?.trim()) sp.set('db_id', params.db_id.trim())
  if (params.table?.trim()) sp.set('table', params.table.trim())
  const q = sp.toString()
  const path = APIRoutes.RefreshMetrics(base)
  const href = q ? `${path}?${q}` : path
  try {
    const response = await agentOsRequest(href, {
      method: 'POST',
      authToken,
    })
    if (!response.ok) {
      return null
    }
    const data: unknown = await response.json()
    return data as AgentOsDayAggregatedMetrics[]
  } catch {
    return null
  }
}

// --- OpenFox（`/config`、`/skills`，OpenAPI 标签 OpenFox / OpenFox Skills）---

export type OpenFoxSkillInfo = {
  /** 是否对 Agent 生效（安装目录名以 `-` 结尾时为 false） */
  activate: boolean
  name: string
  description: string
  license?: string | null
  path: string
}

export type OpenFoxSkillsListResult =
  | { ok: true; data: OpenFoxSkillInfo[] }
  | { ok: false; status: number; message: string }

export async function listOpenFoxSkillsAPI(
  base: string,
  authToken: string | undefined,
): Promise<OpenFoxSkillsListResult> {
  const res = await agentOsRequest(APIRoutes.OpenFoxSkills(base), {
    method: 'GET',
    authToken,
  })
  if (!res.ok) {
    const message = await readAgentOsErrorMessage(res)
    return { ok: false, status: res.status, message }
  }
  const data = (await res.json()) as unknown
  if (!Array.isArray(data)) {
    return {
      ok: false,
      status: 500,
      message: 'Invalid response: expected JSON array',
    }
  }
  return { ok: true, data: data as OpenFoxSkillInfo[] }
}

export type OpenFoxSkillMutationResult =
  | { ok: true; skill: OpenFoxSkillInfo }
  | { ok: false; status: number; message: string }

export async function uploadOpenFoxSkillAPI(
  base: string,
  authToken: string | undefined,
  file: File,
): Promise<OpenFoxSkillMutationResult> {
  const fd = new FormData()
  fd.append('file', file)
  const res = await agentOsRequest(APIRoutes.OpenFoxSkills(base), {
    method: 'POST',
    authToken,
    body: fd,
  })
  if (!res.ok) {
    const message = await readAgentOsErrorMessage(res)
    return { ok: false, status: res.status, message }
  }
  const skill = (await res.json()) as OpenFoxSkillInfo
  return { ok: true, skill }
}

export async function patchOpenFoxSkillActivateAPI(
  base: string,
  authToken: string | undefined,
  diskFolderName: string,
  activate: boolean,
): Promise<OpenFoxSkillMutationResult> {
  const res = await agentOsRequest(
    APIRoutes.OpenFoxSkillActivate(base, diskFolderName),
    {
      method: 'PATCH',
      authToken,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ activate }),
    },
  )
  if (!res.ok) {
    const message = await readAgentOsErrorMessage(res)
    return { ok: false, status: res.status, message }
  }
  const skill = (await res.json()) as OpenFoxSkillInfo
  return { ok: true, skill }
}

export async function replaceOpenFoxSkillAPI(
  base: string,
  authToken: string | undefined,
  name: string,
  file: File,
): Promise<OpenFoxSkillMutationResult> {
  const fd = new FormData()
  fd.append('file', file)
  const res = await agentOsRequest(APIRoutes.OpenFoxSkillByName(base, name), {
    method: 'PUT',
    authToken,
    body: fd,
  })
  if (!res.ok) {
    const message = await readAgentOsErrorMessage(res)
    return { ok: false, status: res.status, message }
  }
  const skill = (await res.json()) as OpenFoxSkillInfo
  return { ok: true, skill }
}

export type OpenFoxSkillDeleteResult =
  | { ok: true }
  | { ok: false; status: number; message: string }

export async function deleteOpenFoxSkillAPI(
  base: string,
  authToken: string | undefined,
  name: string,
): Promise<OpenFoxSkillDeleteResult> {
  const res = await agentOsRequest(APIRoutes.OpenFoxSkillByName(base, name), {
    method: 'DELETE',
    authToken,
  })
  if (!res.ok) {
    const message = await readAgentOsErrorMessage(res)
    return { ok: false, status: res.status, message }
  }
  return { ok: true }
}

export type OpenFoxConfigGetResult =
  | { ok: true; data: Record<string, unknown> }
  | { ok: false; status: number; message: string }

export async function getOpenFoxConfigAPI(
  base: string,
  authToken: string | undefined,
): Promise<OpenFoxConfigGetResult> {
  const res = await agentOsRequest(APIRoutes.OpenFoxConfig(base), {
    method: 'GET',
    authToken,
  })
  if (!res.ok) {
    const message = await readAgentOsErrorMessage(res)
    return { ok: false, status: res.status, message }
  }
  const data = (await res.json()) as Record<string, unknown>
  return { ok: true, data }
}

export type OpenFoxConfigPutResult =
  | { ok: true; path?: string }
  | { ok: false; status: number; message: string }

export async function putOpenFoxConfigAPI(
  base: string,
  authToken: string | undefined,
  body: Record<string, unknown>,
): Promise<OpenFoxConfigPutResult> {
  const res = await agentOsRequest(APIRoutes.OpenFoxConfig(base), {
    method: 'PUT',
    authToken,
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const message = await readAgentOsErrorMessage(res)
    return { ok: false, status: res.status, message }
  }
  try {
    const j = (await res.json()) as { path?: unknown }
    const path = typeof j.path === 'string' ? j.path : undefined
    return { ok: true, path }
  } catch {
    return { ok: true }
  }
}

export type OpenFoxVersionGetResult =
  | { ok: true; version: string }
  | { ok: false; status: number; message: string }

export async function getOpenFoxVersionAPI(
  base: string,
  authToken: string | undefined,
): Promise<OpenFoxVersionGetResult> {
  const res = await agentOsRequest(APIRoutes.OpenFoxVersion(base), {
    method: 'GET',
    authToken,
  })
  if (!res.ok) {
    const message = await readAgentOsErrorMessage(res)
    return { ok: false, status: res.status, message }
  }
  try {
    const data = (await res.json()) as { version?: unknown }
    const version = typeof data.version === 'string' ? data.version.trim() : ''
    if (!version) {
      return { ok: false, status: 500, message: 'Invalid response: missing version' }
    }
    return { ok: true, version }
  } catch {
    return { ok: false, status: 500, message: 'Invalid JSON response' }
  }
}
