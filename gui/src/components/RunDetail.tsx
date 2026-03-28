import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  Terminal,
  Pause,
  Flag,
  Circle,
  Loader2,
  FileText,
  AlertTriangle,
} from "lucide-react";
import { api } from "../lib/api";
import type { StepResult, StepKind } from "../lib/types";
import { StatusBadge } from "./StatusBadge";
import { JsonView } from "./JsonView";
import { cn, timeAgo, formatDuration } from "../lib/utils";

function StepKindIcon({ kind }: { kind: StepKind }) {
  switch (kind) {
    case "cli":
      return <Terminal className="w-4 h-4" />;
    case "await_event":
      return <Pause className="w-4 h-4" />;
    case "end":
      return <Flag className="w-4 h-4" />;
    default:
      return <Circle className="w-4 h-4" />;
  }
}

const kindColors: Record<string, string> = {
  cli: "bg-blue-50 text-blue-700 border-blue-200",
  await_event: "bg-amber-50 text-amber-700 border-amber-200",
  end: "bg-emerald-50 text-emerald-700 border-emerald-200",
};

function StepItem({
  step,
  runId,
  isLast,
}: {
  step: StepResult;
  runId: string;
  isLast: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [showStdout, setShowStdout] = useState(false);
  const [showStderr, setShowStderr] = useState(false);

  const stdoutQuery = useQuery({
    queryKey: ["stdout", runId, step.step_id],
    queryFn: () => api.getStepStdout(runId, step.step_id),
    enabled: showStdout,
    staleTime: 60_000,
  });

  const stderrQuery = useQuery({
    queryKey: ["stderr", runId, step.step_id],
    queryFn: () => api.getStepStderr(runId, step.step_id),
    enabled: showStderr,
    staleTime: 60_000,
  });

  const hasFailed =
    step.exit_code !== null && step.exit_code !== 0;
  const hasError = step.error_code !== null;

  return (
    <div className="flex gap-3">
      {/* Timeline line */}
      <div className="flex flex-col items-center">
        <div
          className={cn(
            "w-8 h-8 rounded-full flex items-center justify-center shrink-0 border",
            hasFailed || hasError
              ? "bg-red-50 text-red-600 border-red-200"
              : kindColors[step.step_kind] ??
                  "bg-zinc-50 text-zinc-500 border-zinc-200"
          )}
        >
          <StepKindIcon kind={step.step_kind} />
        </div>
        {!isLast && <div className="w-px flex-1 bg-zinc-200 my-1" />}
      </div>

      {/* Step content */}
      <div className={cn("flex-1 pb-4", isLast ? "" : "pb-6")}>
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 w-full text-left group"
        >
          {expanded ? (
            <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-zinc-400" />
          )}
          <span className="font-medium text-sm text-zinc-900">
            {step.step_id}
          </span>
          <span
            className={cn(
              "text-xs px-1.5 py-0.5 rounded border font-medium",
              kindColors[step.step_kind] ??
                "bg-zinc-50 text-zinc-500 border-zinc-200"
            )}
          >
            {step.step_kind}
          </span>
          {step.exit_code !== null && (
            <span
              className={cn(
                "text-xs font-mono",
                hasFailed ? "text-red-600" : "text-zinc-400"
              )}
            >
              exit {step.exit_code}
            </span>
          )}
          <span className="text-xs text-zinc-400 ml-auto">
            {timeAgo(step.created_at)}
          </span>
        </button>

        {(hasFailed || hasError) && step.error_message && (
          <div className="mt-2 flex items-start gap-2 p-2 rounded-md bg-red-50 border border-red-200">
            <AlertTriangle className="w-3.5 h-3.5 text-red-500 mt-0.5 shrink-0" />
            <div className="text-xs text-red-700">
              {step.error_code && (
                <span className="font-mono font-medium">
                  [{step.error_code}]{" "}
                </span>
              )}
              {step.error_message}
            </div>
          </div>
        )}

        {expanded && (
          <div className="mt-3 space-y-3 ml-5">
            {/* Outputs */}
            {step.outputs &&
              Object.keys(step.outputs).length > 0 && (
                <div>
                  <div className="text-xs font-medium text-zinc-500 mb-1">
                    Outputs
                  </div>
                  <JsonView data={step.outputs} />
                </div>
              )}

            {/* Stdout */}
            {step.stdout_path && (
              <div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowStdout(!showStdout);
                  }}
                  className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800 font-medium"
                >
                  <FileText className="w-3 h-3" />
                  {showStdout ? "Hide" : "Show"} stdout
                </button>
                {showStdout && (
                  <div className="mt-1">
                    {stdoutQuery.isLoading && (
                      <Loader2 className="w-3 h-3 animate-spin text-zinc-400" />
                    )}
                    {stdoutQuery.data !== undefined && (
                      <pre className="text-xs font-mono bg-zinc-900 text-zinc-100 rounded-lg p-3 overflow-auto max-h-60">
                        {stdoutQuery.data || "(empty)"}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Stderr */}
            {step.stderr_path && (
              <div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowStderr(!showStderr);
                  }}
                  className="flex items-center gap-1.5 text-xs text-red-600 hover:text-red-800 font-medium"
                >
                  <AlertTriangle className="w-3 h-3" />
                  {showStderr ? "Hide" : "Show"} stderr
                </button>
                {showStderr && (
                  <div className="mt-1">
                    {stderrQuery.isLoading && (
                      <Loader2 className="w-3 h-3 animate-spin text-zinc-400" />
                    )}
                    {stderrQuery.data !== undefined && (
                      <pre className="text-xs font-mono bg-red-950 text-red-200 rounded-lg p-3 overflow-auto max-h-60">
                        {stderrQuery.data || "(empty)"}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const [showInputs, setShowInputs] = useState(false);

  const {
    data: run,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["run", id],
    queryFn: () => api.getRun(id!),
    enabled: !!id,
    staleTime: 5_000,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "running" || status === "waiting") return 10_000;
      return false;
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-5 h-5 animate-spin text-zinc-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Failed to load run: {(error as Error).message}
        </div>
      </div>
    );
  }

  if (!run) return null;

  const sortedSteps = [...run.step_results].sort(
    (a, b) => a.execution_order - b.execution_order
  );

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Back link */}
      <Link
        to="/"
        className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-900 mb-4 transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        All Runs
      </Link>

      {/* Header card */}
      <div className="bg-white rounded-xl border border-zinc-200 p-5 mb-6 shadow-sm">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h1 className="text-lg font-semibold text-zinc-900">
              {run.workflow_id}
            </h1>
            <p className="text-xs text-zinc-400 mt-0.5">
              Version {run.workflow_version}
            </p>
          </div>
          <StatusBadge status={run.status} />
        </div>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-xs text-zinc-400 mb-0.5">Run ID</div>
            <div className="font-mono text-xs text-zinc-700">
              {run.run_id}
            </div>
          </div>
          <div>
            <div className="text-xs text-zinc-400 mb-0.5">Created</div>
            <div className="text-xs text-zinc-700">
              {timeAgo(run.created_at)}
            </div>
          </div>
          <div>
            <div className="text-xs text-zinc-400 mb-0.5">Duration</div>
            <div className="text-xs text-zinc-700">
              {formatDuration(run.created_at, run.updated_at)}
            </div>
          </div>
        </div>
      </div>

      {/* Inputs */}
      {run.inputs && Object.keys(run.inputs).length > 0 && (
        <div className="mb-6">
          <button
            onClick={() => setShowInputs(!showInputs)}
            className="flex items-center gap-2 text-sm font-medium text-zinc-700 hover:text-zinc-900"
          >
            {showInputs ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5" />
            )}
            Inputs
          </button>
          {showInputs && (
            <div className="mt-2">
              <JsonView data={run.inputs} />
            </div>
          )}
        </div>
      )}

      {/* Step timeline */}
      <div className="mb-6">
        <h2 className="text-sm font-medium text-zinc-700 mb-4">
          Step Execution
        </h2>
        <div className="bg-white rounded-xl border border-zinc-200 p-5 shadow-sm">
          {sortedSteps.length === 0 ? (
            <p className="text-sm text-zinc-400 text-center py-4">
              No steps executed yet
            </p>
          ) : (
            sortedSteps.map((step, i) => (
              <StepItem
                key={`${step.step_id}-${step.execution_order}`}
                step={step}
                runId={run.run_id}
                isLast={i === sortedSteps.length - 1}
              />
            ))
          )}
        </div>
      </div>

      {/* Events */}
      {run.events && run.events.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-medium text-zinc-700 mb-4">Events</h2>
          <div className="space-y-2">
            {run.events.map((event, i) => (
              <div
                key={i}
                className="bg-white rounded-xl border border-zinc-200 p-4 shadow-sm"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-zinc-900">
                    {event.event_name}
                  </span>
                  <span className="text-xs text-zinc-400">
                    {timeAgo(event.created_at)}
                  </span>
                </div>
                <JsonView data={event.event_data} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Result */}
      {run.result !== null && run.result !== undefined && (
        <div className="mb-6">
          <h2 className="text-sm font-medium text-zinc-700 mb-4">Result</h2>
          <div className="bg-white rounded-xl border border-zinc-200 p-4 shadow-sm">
            <JsonView data={run.result} />
          </div>
        </div>
      )}
    </div>
  );
}
