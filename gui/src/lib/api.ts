import type {
  RunSummary,
  RunDetail,
  WorkflowFile,
  WorkflowDetail,
} from "./types";

const BASE = "/api";

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function fetchText(url: string): Promise<string> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.text();
}

export const api = {
  getRuns(): Promise<RunSummary[]> {
    return fetchJSON<RunSummary[]>(`${BASE}/runs`);
  },

  getRun(id: string): Promise<RunDetail> {
    return fetchJSON<RunDetail>(`${BASE}/runs/${id}`);
  },

  getStepStdout(runId: string, stepId: string): Promise<string> {
    return fetchText(`${BASE}/runs/${runId}/steps/${stepId}/stdout`);
  },

  getStepStderr(runId: string, stepId: string): Promise<string> {
    return fetchText(`${BASE}/runs/${runId}/steps/${stepId}/stderr`);
  },

  getWorkflows(): Promise<WorkflowFile[]> {
    return fetchJSON<WorkflowFile[]>(`${BASE}/workflows`);
  },

  getWorkflow(path: string): Promise<WorkflowDetail> {
    return fetchJSON<WorkflowDetail>(
      `${BASE}/workflows?path=${encodeURIComponent(path)}`
    );
  },
};
