import { agentOsRequest, readAgentOsErrorMessage } from "@/composables/request"
import { APIRoutes } from "./routes"

type PaginatedMeta = {
  page: number
  limit: number
  total_pages: number
  total_count: number
  search_time_ms?: number
}

type PaginatedData<T> = {
  data: T[]
  meta: PaginatedMeta
}

type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; message: string }

export type TraceSummary = {
  trace_id: string
  name: string
  status: string
  duration: string
  start_time: string
  end_time: string
  total_spans: number
  error_count: number
  input?: string | null
  run_id?: string | null
  session_id?: string | null
  user_id?: string | null
  agent_id?: string | null
  team_id?: string | null
  workflow_id?: string | null
  created_at: string
}

export type TraceSessionStats = {
  session_id: string
  user_id?: string | null
  agent_id?: string | null
  team_id?: string | null
  workflow_id?: string | null
  total_traces: number
  first_trace_at: string
  last_trace_at: string
}

export type TraceNode = {
  id: string
  name: string
  type: string
  duration: string
  start_time: string
  end_time: string
  status: string
  input?: string | null
  output?: string | null
  error?: string | null
  spans?: TraceNode[] | null
  step_type?: string | null
  metadata?: Record<string, unknown> | null
  extra_data?: Record<string, unknown> | null
}

export type TraceDetail = {
  trace_id: string
  name: string
  status: string
  duration: string
  start_time: string
  end_time: string
  total_spans: number
  error_count: number
  input?: string | null
  output?: string | null
  error?: string | null
  run_id?: string | null
  session_id?: string | null
  user_id?: string | null
  agent_id?: string | null
  team_id?: string | null
  workflow_id?: string | null
  created_at: string
  tree: TraceNode[]
}

export async function listTracesAPI(
  base: string,
  authToken: string | undefined,
  params: {
    run_id?: string
    session_id?: string
    user_id?: string
    agent_id?: string
    team_id?: string
    workflow_id?: string
    status?: string
    start_time?: string
    end_time?: string
    page?: number
    limit?: number
    db_id?: string
  } = {},
): Promise<ApiResult<PaginatedData<TraceSummary>>> {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v == null || v === "") continue
    sp.set(k, String(v))
  }
  const q = sp.toString()
  const path = APIRoutes.Traces(base)
  const href = q ? `${path}?${q}` : path
  try {
    const res = await agentOsRequest(href, { method: "GET", authToken })
    if (!res.ok) {
      const message = await readAgentOsErrorMessage(res)
      return { ok: false, status: res.status, message }
    }
    const data = (await res.json()) as PaginatedData<TraceSummary>
    return { ok: true, data }
  } catch (e) {
    return {
      ok: false,
      status: 0,
      message: e instanceof Error ? e.message : "Network error",
    }
  }
}

export async function listTraceSessionStatsAPI(
  base: string,
  authToken: string | undefined,
  params: {
    user_id?: string
    agent_id?: string
    team_id?: string
    workflow_id?: string
    start_time?: string
    end_time?: string
    page?: number
    limit?: number
    db_id?: string
  } = {},
): Promise<ApiResult<PaginatedData<TraceSessionStats>>> {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v == null || v === "") continue
    sp.set(k, String(v))
  }
  const q = sp.toString()
  const path = APIRoutes.TraceSessionStats(base)
  const href = q ? `${path}?${q}` : path
  try {
    const res = await agentOsRequest(href, { method: "GET", authToken })
    if (!res.ok) {
      const message = await readAgentOsErrorMessage(res)
      return { ok: false, status: res.status, message }
    }
    const data = (await res.json()) as PaginatedData<TraceSessionStats>
    return { ok: true, data }
  } catch (e) {
    return {
      ok: false,
      status: 0,
      message: e instanceof Error ? e.message : "Network error",
    }
  }
}

export async function getTraceDetailAPI(
  base: string,
  authToken: string | undefined,
  traceId: string,
  params: { span_id?: string; run_id?: string; db_id?: string } = {},
): Promise<ApiResult<TraceDetail | TraceNode>> {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v == null || v === "") continue
    sp.set(k, String(v))
  }
  const q = sp.toString()
  const path = APIRoutes.TraceById(base, traceId)
  const href = q ? `${path}?${q}` : path
  try {
    const res = await agentOsRequest(href, { method: "GET", authToken })
    if (!res.ok) {
      const message = await readAgentOsErrorMessage(res)
      return { ok: false, status: res.status, message }
    }
    const data = (await res.json()) as TraceDetail | TraceNode
    return { ok: true, data }
  } catch (e) {
    return {
      ok: false,
      status: 0,
      message: e instanceof Error ? e.message : "Network error",
    }
  }
}
