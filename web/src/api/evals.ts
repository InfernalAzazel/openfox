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

export type EvalType =
  | "accuracy"
  | "agent_as_judge"
  | "performance"
  | "reliability"

export type EvalRun = {
  id: string
  agent_id?: string | null
  model_id?: string | null
  model_provider?: string | null
  team_id?: string | null
  workflow_id?: string | null
  name?: string | null
  evaluated_component_name?: string | null
  eval_type: EvalType
  eval_data: Record<string, unknown>
  eval_input?: Record<string, unknown> | null
  created_at?: string | null
  updated_at?: string | null
}

export type EvalRunInput = {
  agent_id?: string | null
  team_id?: string | null
  model_id?: string | null
  model_provider?: string | null
  eval_type: EvalType
  input: string
  additional_guidelines?: string | null
  additional_context?: string | null
  num_iterations?: number
  name?: string | null
  expected_output?: string | null
  criteria?: string | null
  scoring_strategy?: "numeric" | "binary" | null
  threshold?: number | null
  warmup_runs?: number
  expected_tool_calls?: string[] | null
  allow_additional_tool_calls?: boolean
}

export async function getEvalRunAPI(
  base: string,
  authToken: string | undefined,
  evalRunId: string,
  query: { db_id?: string; table?: string } = {},
): Promise<ApiResult<EvalRun>> {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v == null || v === "") continue
    sp.set(k, String(v))
  }
  const q = sp.toString()
  const path = APIRoutes.EvalRunById(base, evalRunId)
  const href = q ? `${path}?${q}` : path
  try {
    const res = await agentOsRequest(href, { method: "GET", authToken })
    if (!res.ok) {
      const message = await readAgentOsErrorMessage(res)
      return { ok: false, status: res.status, message }
    }
    const data = (await res.json()) as EvalRun
    return { ok: true, data }
  } catch (e) {
    return {
      ok: false,
      status: 0,
      message: e instanceof Error ? e.message : "Network error",
    }
  }
}

export async function listEvalRunsAPI(
  base: string,
  authToken: string | undefined,
  params: {
    agent_id?: string
    team_id?: string
    workflow_id?: string
    model_id?: string
    type?: string
    limit?: number
    page?: number
    sort_by?: string
    sort_order?: string
    db_id?: string
    table?: string
  } = {},
): Promise<ApiResult<PaginatedData<EvalRun>>> {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v == null || v === "") continue
    sp.set(k, String(v))
  }
  const q = sp.toString()
  const path = APIRoutes.EvalRuns(base)
  const href = q ? `${path}?${q}` : path
  try {
    const res = await agentOsRequest(href, { method: "GET", authToken })
    if (!res.ok) {
      const message = await readAgentOsErrorMessage(res)
      return { ok: false, status: res.status, message }
    }
    const data = (await res.json()) as PaginatedData<EvalRun>
    return { ok: true, data }
  } catch (e) {
    return {
      ok: false,
      status: 0,
      message: e instanceof Error ? e.message : "Network error",
    }
  }
}

export async function runEvalAPI(
  base: string,
  authToken: string | undefined,
  body: EvalRunInput,
  query: { db_id?: string; table?: string } = {},
): Promise<ApiResult<EvalRun>> {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v == null || v === "") continue
    sp.set(k, String(v))
  }
  const q = sp.toString()
  const path = APIRoutes.EvalRuns(base)
  const href = q ? `${path}?${q}` : path
  try {
    const res = await agentOsRequest(href, {
      method: "POST",
      authToken,
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const message = await readAgentOsErrorMessage(res)
      return { ok: false, status: res.status, message }
    }
    const data = (await res.json()) as EvalRun
    return { ok: true, data }
  } catch (e) {
    return {
      ok: false,
      status: 0,
      message: e instanceof Error ? e.message : "Network error",
    }
  }
}

export async function deleteEvalRunsAPI(
  base: string,
  authToken: string | undefined,
  evalRunIds: string[],
  query: { db_id?: string; table?: string } = {},
): Promise<ApiResult<void>> {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v == null || v === "") continue
    sp.set(k, String(v))
  }
  const q = sp.toString()
  const path = APIRoutes.EvalRuns(base)
  const href = q ? `${path}?${q}` : path
  try {
    const res = await agentOsRequest(href, {
      method: "DELETE",
      authToken,
      body: JSON.stringify({ eval_run_ids: evalRunIds }),
    })
    if (!res.ok) {
      const message = await readAgentOsErrorMessage(res)
      return { ok: false, status: res.status, message }
    }
    return { ok: true, data: undefined }
  } catch (e) {
    return {
      ok: false,
      status: 0,
      message: e instanceof Error ? e.message : "Network error",
    }
  }
}
