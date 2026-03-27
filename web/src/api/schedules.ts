/**
 * AgentOS Schedules API（OpenAPI 10 个操作）
 * @see http://127.0.0.1:7777/docs#/Schedules
 */
import { agentOsRequest, readAgentOsErrorMessage } from '@/composables/request'
import type {
  PaginatedScheduleRunsResponse,
  PaginatedSchedulesResponse,
  ScheduleCreate,
  ScheduleResponse,
  ScheduleRunResponse,
  ScheduleUpdate,
} from '@/types/schedules'
import { APIRoutes } from './routes'

export async function listSchedulesAPI(
  base: string,
  authToken: string | undefined,
  params?: { enabled?: boolean | null; limit?: number; page?: number },
): Promise<PaginatedSchedulesResponse | null> {
  const sp = new URLSearchParams()
  if (params?.enabled != null) {
    sp.set('enabled', String(params.enabled))
  }
  if (params?.limit != null) {
    sp.set('limit', String(params.limit))
  }
  if (params?.page != null) {
    sp.set('page', String(params.page))
  }
  const q = sp.toString()
  const url = `${APIRoutes.ListSchedules(base)}${q ? `?${q}` : ''}`
  const res = await agentOsRequest(url, { method: 'GET', authToken })
  if (!res.ok) {
    return null
  }
  return (await res.json()) as PaginatedSchedulesResponse
}

export type CreateScheduleResult =
  | { ok: true; data: ScheduleResponse }
  | { ok: false; status: number; message: string }

export async function createScheduleAPI(
  base: string,
  authToken: string | undefined,
  body: ScheduleCreate,
): Promise<CreateScheduleResult> {
  const res = await agentOsRequest(APIRoutes.CreateSchedule(base), {
    method: 'POST',
    authToken,
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const message = await readAgentOsErrorMessage(res)
    return { ok: false, status: res.status, message }
  }
  const data = (await res.json()) as ScheduleResponse
  return { ok: true, data }
}

export async function getScheduleAPI(
  base: string,
  authToken: string | undefined,
  scheduleId: string,
): Promise<ScheduleResponse | null> {
  const res = await agentOsRequest(APIRoutes.GetSchedule(base, scheduleId), {
    method: 'GET',
    authToken,
  })
  if (!res.ok) {
    return null
  }
  return (await res.json()) as ScheduleResponse
}

export async function patchScheduleAPI(
  base: string,
  authToken: string | undefined,
  scheduleId: string,
  body: ScheduleUpdate,
): Promise<ScheduleResponse | null> {
  const res = await agentOsRequest(APIRoutes.PatchSchedule(base, scheduleId), {
    method: 'PATCH',
    authToken,
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    return null
  }
  return (await res.json()) as ScheduleResponse
}

export async function deleteScheduleAPI(
  base: string,
  authToken: string | undefined,
  scheduleId: string,
): Promise<boolean> {
  const res = await agentOsRequest(APIRoutes.DeleteSchedule(base, scheduleId), {
    method: 'DELETE',
    authToken,
  })
  return res.ok
}

export async function enableScheduleAPI(
  base: string,
  authToken: string | undefined,
  scheduleId: string,
): Promise<boolean> {
  const res = await agentOsRequest(APIRoutes.EnableSchedule(base, scheduleId), {
    method: 'POST',
    authToken,
  })
  return res.ok
}

export async function disableScheduleAPI(
  base: string,
  authToken: string | undefined,
  scheduleId: string,
): Promise<boolean> {
  const res = await agentOsRequest(APIRoutes.DisableSchedule(base, scheduleId), {
    method: 'POST',
    authToken,
  })
  return res.ok
}

export async function triggerScheduleAPI(
  base: string,
  authToken: string | undefined,
  scheduleId: string,
): Promise<boolean> {
  const res = await agentOsRequest(APIRoutes.TriggerSchedule(base, scheduleId), {
    method: 'POST',
    authToken,
  })
  return res.ok
}

export async function listScheduleRunsAPI(
  base: string,
  authToken: string | undefined,
  scheduleId: string,
  params?: { limit?: number; page?: number },
): Promise<PaginatedScheduleRunsResponse | null> {
  const sp = new URLSearchParams()
  if (params?.limit != null) {
    sp.set('limit', String(params.limit))
  }
  if (params?.page != null) {
    sp.set('page', String(params.page))
  }
  const q = sp.toString()
  const url = `${APIRoutes.ListScheduleRuns(base, scheduleId)}${q ? `?${q}` : ''}`
  const res = await agentOsRequest(url, {
    method: 'GET',
    authToken,
  })
  if (!res.ok) {
    return null
  }
  return (await res.json()) as PaginatedScheduleRunsResponse
}

export async function getScheduleRunAPI(
  base: string,
  authToken: string | undefined,
  scheduleId: string,
  runId: string,
): Promise<ScheduleRunResponse | null> {
  const res = await agentOsRequest(
    APIRoutes.GetScheduleRun(base, scheduleId, runId),
    { method: 'GET', authToken },
  )
  if (!res.ok) {
    return null
  }
  return (await res.json()) as ScheduleRunResponse
}
