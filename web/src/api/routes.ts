/** Aligned with [agent-ui APIRoutes](https://github.com/agno-agi/agent-ui/blob/main/src/api/routes.ts). */

export const APIRoutes = {
  GetAgents: (agentOSUrl: string) => `${agentOSUrl}/agents`,
  AgentRun: (agentOSUrl: string, agentId: string) =>
    `${agentOSUrl.replace(/\/$/, '')}/agents/${encodeURIComponent(agentId)}/runs`,
  Status: (agentOSUrl: string) => `${agentOSUrl}/health`,
  GetSessions: (agentOSUrl: string) => `${agentOSUrl}/sessions`,
  GetSession: (agentOSUrl: string, sessionId: string) =>
    `${agentOSUrl}/sessions/${sessionId}/runs`,

  DeleteSession: (agentOSUrl: string, sessionId: string) =>
    `${agentOSUrl}/sessions/${sessionId}`,

  GetTeams: (agentOSUrl: string) => `${agentOSUrl}/teams`,
  TeamRun: (agentOSUrl: string, teamId: string) =>
    `${agentOSUrl.replace(/\/$/, '')}/teams/${encodeURIComponent(teamId)}/runs`,
  DeleteTeamSession: (agentOSUrl: string, teamId: string, sessionId: string) =>
    `${agentOSUrl}/v1//teams/${teamId}/sessions/${sessionId}`,

  /** @see OpenAPI `GET /metrics` */
  GetMetrics: (agentOSUrl: string) => `${agentOSUrl}/metrics`,
  /** @see OpenAPI `POST /metrics/refresh` */
  RefreshMetrics: (agentOSUrl: string) => `${agentOSUrl}/metrics/refresh`,

  /** @see OpenAPI tag `Schedules` */
  ListSchedules: (agentOSUrl: string) => `${agentOSUrl.replace(/\/$/, '')}/schedules`,
  CreateSchedule: (agentOSUrl: string) => `${agentOSUrl.replace(/\/$/, '')}/schedules`,
  GetSchedule: (agentOSUrl: string, scheduleId: string) =>
    `${agentOSUrl.replace(/\/$/, '')}/schedules/${encodeURIComponent(scheduleId)}`,
  PatchSchedule: (agentOSUrl: string, scheduleId: string) =>
    `${agentOSUrl.replace(/\/$/, '')}/schedules/${encodeURIComponent(scheduleId)}`,
  DeleteSchedule: (agentOSUrl: string, scheduleId: string) =>
    `${agentOSUrl.replace(/\/$/, '')}/schedules/${encodeURIComponent(scheduleId)}`,
  EnableSchedule: (agentOSUrl: string, scheduleId: string) =>
    `${agentOSUrl.replace(/\/$/, '')}/schedules/${encodeURIComponent(scheduleId)}/enable`,
  DisableSchedule: (agentOSUrl: string, scheduleId: string) =>
    `${agentOSUrl.replace(/\/$/, '')}/schedules/${encodeURIComponent(scheduleId)}/disable`,
  TriggerSchedule: (agentOSUrl: string, scheduleId: string) =>
    `${agentOSUrl.replace(/\/$/, '')}/schedules/${encodeURIComponent(scheduleId)}/trigger`,
  ListScheduleRuns: (agentOSUrl: string, scheduleId: string) =>
    `${agentOSUrl.replace(/\/$/, '')}/schedules/${encodeURIComponent(scheduleId)}/runs`,
  GetScheduleRun: (agentOSUrl: string, scheduleId: string, runId: string) =>
    `${agentOSUrl.replace(/\/$/, '')}/schedules/${encodeURIComponent(scheduleId)}/runs/${encodeURIComponent(runId)}`,

  /** OpenFox: `GET` / `PUT` `/config` (OpenAPI tag `OpenFox`). */
  OpenFoxConfig: (agentOSUrl: string) =>
    `${agentOSUrl.replace(/\/$/, '')}/expand/config`,

  /** OpenFox: `GET` / `POST` `/skills`, `PATCH /skills/activate/{name}`, `PUT` / `DELETE` `/skills/{name}` */
  OpenFoxSkills: (agentOSUrl: string) =>
    `${agentOSUrl.replace(/\/$/, '')}/expand/skills`,
  OpenFoxSkillByName: (agentOSUrl: string, name: string) =>
    `${agentOSUrl.replace(/\/$/, '')}/expand/skills/${encodeURIComponent(name)}`,
  /** OpenFox: `PATCH` body `{ activate }` */
  OpenFoxSkillActivate: (agentOSUrl: string, name: string) =>
    `${agentOSUrl.replace(/\/$/, '')}/expand/skills/activate/${encodeURIComponent(name)}`,
}
