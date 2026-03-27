/** OpenAPI `Schedules` 标签，与 AgentOS `/schedules` 对齐 */

export interface ScheduleCreate {
  name: string
  cron_expr: string
  endpoint: string
  method?: string
  description?: string | null
  payload?: Record<string, unknown> | null
  timezone?: string
  timeout_seconds?: number
  max_retries?: number
  retry_delay_seconds?: number
}

export interface ScheduleUpdate {
  name?: string | null
  cron_expr?: string | null
  endpoint?: string | null
  method?: string | null
  description?: string | null
  payload?: Record<string, unknown> | null
  timezone?: string | null
  timeout_seconds?: number | null
  max_retries?: number | null
  retry_delay_seconds?: number | null
}

export interface ScheduleResponse {
  id: string
  name: string
  description: string | null
  method: string
  endpoint: string
  payload: Record<string, unknown> | null
  cron_expr: string
  timezone: string
  timeout_seconds: number
  max_retries: number
  retry_delay_seconds: number
  enabled: boolean
  next_run_at: number | null
  created_at: number | null
  updated_at: number | null
}

export interface PaginationInfo {
  page: number
  limit: number
  total_pages: number
  total_count: number
  search_time_ms?: number
}

export interface PaginatedSchedulesResponse {
  data: ScheduleResponse[]
  meta: PaginationInfo
}

export interface ScheduleRunResponse {
  id: string
  schedule_id: string
  attempt: number
  triggered_at: number | null
  completed_at: number | null
  status: string
  status_code: number | null
  run_id: string | null
  session_id: string | null
  error: string | null
  input: Record<string, unknown> | null
  output: Record<string, unknown> | null
  requirements?: unknown[] | null
  created_at: number | null
}

export interface PaginatedScheduleRunsResponse {
  data: ScheduleRunResponse[]
  meta: PaginationInfo
}
