export interface RunSummary {
  run_id: string;
  workflow_id: string;
  workflow_version: string;
  workflow_path: string;
  status: RunStatus;
  current_step_id: string | null;
  created_at: string;
  updated_at: string;
}

export type RunStatus =
  | "running"
  | "completed"
  | "failed"
  | "waiting"
  | "cancelled";

export interface RunDetail extends RunSummary {
  inputs: Record<string, unknown>;
  step_outputs: Record<string, unknown>;
  result: unknown;
  step_results: StepResult[];
  events: RunEvent[];
}

export interface StepResult {
  step_id: string;
  step_kind: StepKind;
  exit_code: number | null;
  error_code: string | null;
  error_message: string | null;
  outputs: Record<string, unknown>;
  stdout_path: string | null;
  stderr_path: string | null;
  execution_order: number;
  created_at: string;
}

export type StepKind = "cli" | "await_event" | "end" | string;

export interface RunEvent {
  event_name: string;
  event_data: Record<string, unknown>;
  created_at: string;
}

export interface WorkflowFile {
  path: string;
  name: string;
  source: string;
  relative: string;
}

export interface WorkflowDetail {
  id: string;
  name: string;
  version: string;
  description: string;
  defaults: Record<string, unknown>;
  inputs: Record<string, unknown>;
  steps: WorkflowStep[];
  path: string;
}

export interface WorkflowStep {
  id: string;
  kind: StepKind;
  name: string;
  description: string;
  if?: string;
  index: number;
  command?: string;
  shell?: string;
  cwd?: string;
  audience?: string;
  event_name?: string;
  prompt?: string;
  transitions?: Transition[];
  result?: unknown;
}

export interface Transition {
  when: string;
  next: string;
}
