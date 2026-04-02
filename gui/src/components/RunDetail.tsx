import { useState, useContext } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import {
  Button,
  Spinner,
  makeStyles,
  tokens,
  Dialog,
  DialogSurface,
  DialogBody,
  DialogTitle,
  DialogActions,
  DialogContent,
  Toast,
  ToastBody,
} from "@fluentui/react-components";
import {
  ChevronDownRegular,
  ChevronRightRegular,
  DeleteRegular,
  DocumentTextRegular,
  WarningRegular,
} from "@fluentui/react-icons";
import { Terminal, Pause, Flag, Circle } from "lucide-react";
import { api } from "../lib/api";
import type { StepResult, StepKind } from "../lib/types";
import { StatusBadge } from "./StatusBadge";
import { JsonView } from "./JsonView";
import { CopyButton } from "./CopyButton";
import { timeAgo, formatDuration } from "../lib/utils";
import { ToasterContext } from "../App";
import type { DockviewPanelApi } from "dockview";

function StepKindIcon({ kind }: { kind: StepKind }) {
  const s = { width: 16, height: 16 };
  switch (kind) {
    case "cli":
      return <Terminal style={s} />;
    case "await_event":
      return <Pause style={s} />;
    case "end":
      return <Flag style={s} />;
    default:
      return <Circle style={s} />;
  }
}

const kindColors: Record<string, { bg: string; text: string; border: string }> =
  {
    cli: { bg: "#eff6ff", text: "#1e40af", border: "#bfdbfe" },
    await_event: { bg: "#fffbeb", text: "#92400e", border: "#fde68a" },
    end: { bg: "#ecfdf5", text: "#065f46", border: "#a7f3d0" },
  };

const defaultKindColor = { bg: "#fafafa", text: "#52525b", border: "#e4e4e7" };

const useStyles = makeStyles({
  root: {
    padding: "24px",
    maxWidth: "900px",
    marginLeft: "auto",
    marginRight: "auto",
  },
  card: {
    backgroundColor: tokens.colorNeutralBackground1,
    borderRadius: "12px",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    padding: "20px",
    marginBottom: "24px",
  },
  cardHeader: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    marginBottom: "12px",
  },
  title: {
    fontSize: "18px",
    fontWeight: 600,
    color: tokens.colorNeutralForeground1,
    margin: 0,
  },
  version: {
    fontSize: "12px",
    color: tokens.colorNeutralForeground4,
    marginTop: "2px",
  },
  headerActions: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  metaGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr 1fr",
    gap: "16px",
    fontSize: "13px",
  },
  metaLabel: {
    fontSize: "12px",
    color: tokens.colorNeutralForeground4,
    marginBottom: "2px",
  },
  metaValue: {
    fontSize: "12px",
    color: tokens.colorNeutralForeground2,
    display: "flex",
    alignItems: "center",
    gap: "4px",
    fontFamily: "monospace",
  },
  sectionTitle: {
    fontSize: "13px",
    fontWeight: 500,
    color: tokens.colorNeutralForeground2,
    marginBottom: "16px",
    margin: 0,
  },
  sectionToggle: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    fontSize: "13px",
    fontWeight: 500,
    color: tokens.colorNeutralForeground2,
    cursor: "pointer",
    border: "none",
    backgroundColor: "transparent",
    padding: 0,
  },
  mb6: {
    marginBottom: "24px",
  },
  center: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    height: "100%",
  },
  error: {
    padding: "16px",
    borderRadius: "8px",
    border: `1px solid ${tokens.colorPaletteRedBorder2}`,
    backgroundColor: tokens.colorPaletteRedBackground1,
    color: tokens.colorPaletteRedForeground1,
    fontSize: "13px",
    margin: "24px",
  },
  timeline: {
    display: "flex",
    gap: "12px",
  },
  timelineTrack: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
  },
  timelineIcon: {
    width: "32px",
    height: "32px",
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  timelineLine: {
    width: "1px",
    flex: 1,
    backgroundColor: tokens.colorNeutralStroke2,
    marginTop: "4px",
    marginBottom: "4px",
  },
  stepContent: {
    flex: 1,
    paddingBottom: "24px",
  },
  stepHeader: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    width: "100%",
    border: "none",
    backgroundColor: "transparent",
    padding: 0,
    textAlign: "left",
    cursor: "pointer",
  },
  stepName: {
    fontWeight: 500,
    fontSize: "13px",
    color: tokens.colorNeutralForeground1,
  },
  stepKindBadge: {
    fontSize: "11px",
    padding: "2px 6px",
    borderRadius: "4px",
    fontWeight: 500,
  },
  exitCode: {
    fontSize: "12px",
    fontFamily: "monospace",
  },
  stepTime: {
    fontSize: "12px",
    color: tokens.colorNeutralForeground4,
    marginLeft: "auto",
  },
  stepError: {
    marginTop: "8px",
    display: "flex",
    alignItems: "flex-start",
    gap: "8px",
    padding: "8px",
    borderRadius: "6px",
    backgroundColor: tokens.colorPaletteRedBackground1,
    border: `1px solid ${tokens.colorPaletteRedBorder2}`,
  },
  stepErrorText: {
    fontSize: "12px",
    color: tokens.colorPaletteRedForeground1,
  },
  expanded: {
    marginTop: "12px",
    marginLeft: "20px",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  outputLabel: {
    fontSize: "12px",
    fontWeight: 500,
    color: tokens.colorNeutralForeground3,
    marginBottom: "4px",
  },
  stdPre: {
    fontSize: "12px",
    fontFamily: "monospace",
    borderRadius: "8px",
    padding: "12px",
    overflowX: "auto",
    maxHeight: "240px",
    margin: 0,
    position: "relative",
  },
  eventCard: {
    backgroundColor: tokens.colorNeutralBackground1,
    borderRadius: "12px",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    padding: "16px",
  },
  eventHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: "8px",
  },
  eventName: {
    fontSize: "13px",
    fontWeight: 500,
    color: tokens.colorNeutralForeground1,
  },
  audienceBadge: {
    fontSize: "10px",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    padding: "2px 6px",
    borderRadius: "9999px",
    backgroundColor: tokens.colorNeutralBackground3,
    color: tokens.colorNeutralForeground3,
    fontWeight: 500,
  },
  emptySteps: {
    fontSize: "13px",
    color: tokens.colorNeutralForeground4,
    textAlign: "center",
    padding: "16px 0",
  },
});

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
  const styles = useStyles();

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

  const hasFailed = step.exit_code !== null && step.exit_code !== 0;
  const hasError = step.error_code !== null;
  const hasExpandableContent =
    (step.outputs && Object.keys(step.outputs).length > 0) ||
    step.stdout_path !== null ||
    step.stderr_path !== null;

  const kc = kindColors[step.step_kind] ?? defaultKindColor;

  return (
    <div className={styles.timeline}>
      <div className={styles.timelineTrack}>
        <div
          className={styles.timelineIcon}
          style={{
            backgroundColor: hasFailed || hasError ? "#fef2f2" : kc.bg,
            color: hasFailed || hasError ? "#dc2626" : kc.text,
            border: `1px solid ${hasFailed || hasError ? "#fecaca" : kc.border}`,
          }}
        >
          <StepKindIcon kind={step.step_kind} />
        </div>
        {!isLast && <div className={styles.timelineLine} />}
      </div>

      <div className={styles.stepContent}>
        <button
          onClick={() => hasExpandableContent && setExpanded(!expanded)}
          className={styles.stepHeader}
          style={{ cursor: hasExpandableContent ? "pointer" : "default" }}
        >
          {hasExpandableContent ? (
            expanded ? (
              <ChevronDownRegular style={{ width: 14, height: 14 }} />
            ) : (
              <ChevronRightRegular style={{ width: 14, height: 14 }} />
            )
          ) : (
            <span style={{ width: 14, height: 14, flexShrink: 0 }} />
          )}
          <span className={styles.stepName}>{step.step_id}</span>
          <span
            className={styles.stepKindBadge}
            style={{
              backgroundColor: kc.bg,
              color: kc.text,
              border: `1px solid ${kc.border}`,
            }}
          >
            {step.step_kind}
          </span>
          {step.exit_code !== null && (
            <span
              className={styles.exitCode}
              style={{ color: hasFailed ? "#dc2626" : "#a1a1aa" }}
            >
              exit {step.exit_code}
            </span>
          )}
          <span className={styles.stepTime}>{timeAgo(step.created_at)}</span>
        </button>

        {(hasFailed || hasError) && step.error_message && (
          <div className={styles.stepError}>
            <WarningRegular
              style={{
                width: 14,
                height: 14,
                color: "#dc2626",
                marginTop: 2,
                flexShrink: 0,
              }}
            />
            <div className={styles.stepErrorText}>
              {step.error_code && (
                <span style={{ fontFamily: "monospace", fontWeight: 500 }}>
                  [{step.error_code}]{" "}
                </span>
              )}
              {step.error_message}
            </div>
          </div>
        )}

        {expanded && (
          <div className={styles.expanded}>
            {step.outputs && Object.keys(step.outputs).length > 0 && (
              <div>
                <div className={styles.outputLabel}>Outputs</div>
                <JsonView data={step.outputs} />
              </div>
            )}

            {step.stdout_path && (
              <div>
                <Button
                  appearance="subtle"
                  size="small"
                  icon={<DocumentTextRegular />}
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowStdout(!showStdout);
                  }}
                >
                  {showStdout ? "Hide" : "Show"} stdout
                </Button>
                {showStdout && (
                  <div style={{ marginTop: 4 }}>
                    {stdoutQuery.isLoading && <Spinner size="tiny" />}
                    {stdoutQuery.data !== undefined && (
                      <div style={{ position: "relative" }}>
                        <pre
                          className={styles.stdPre}
                          style={{
                            backgroundColor: "#18181b",
                            color: "#f4f4f5",
                          }}
                        >
                          {stdoutQuery.data || "(empty)"}
                        </pre>
                        {stdoutQuery.data && (
                          <div
                            style={{
                              position: "absolute",
                              top: 8,
                              right: 8,
                            }}
                          >
                            <CopyButton
                              text={stdoutQuery.data}
                              label="Copy stdout"
                            />
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {step.stderr_path && (
              <div>
                <Button
                  appearance="subtle"
                  size="small"
                  icon={<WarningRegular />}
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowStderr(!showStderr);
                  }}
                >
                  {showStderr ? "Hide" : "Show"} stderr
                </Button>
                {showStderr && (
                  <div style={{ marginTop: 4 }}>
                    {stderrQuery.isLoading && <Spinner size="tiny" />}
                    {stderrQuery.data !== undefined && (
                      <div style={{ position: "relative" }}>
                        <pre
                          className={styles.stdPre}
                          style={{
                            backgroundColor: "#1c0a0a",
                            color: "#fca5a5",
                          }}
                        >
                          {stderrQuery.data || "(empty)"}
                        </pre>
                        {stderrQuery.data && (
                          <div
                            style={{
                              position: "absolute",
                              top: 8,
                              right: 8,
                            }}
                          >
                            <CopyButton
                              text={stderrQuery.data}
                              label="Copy stderr"
                            />
                          </div>
                        )}
                      </div>
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

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

export function RunDetail({
  runId,
  panelApi,
}: {
  runId: string;
  panelApi: DockviewPanelApi;
}) {
  const queryClient = useQueryClient();
  const toastController = useContext(ToasterContext);
  const styles = useStyles();
  const [showInputs, setShowInputs] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteRun(runId),
    onSuccess: () => {
      toastController?.dispatchToast(
        <Toast>
          <ToastBody>Run deleted</ToastBody>
        </Toast>,
        { intent: "success" },
      );
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      panelApi.close();
    },
    onError: (err: Error) => {
      toastController?.dispatchToast(
        <Toast>
          <ToastBody>Delete failed: {err.message}</ToastBody>
        </Toast>,
        { intent: "error" },
      );
    },
  });

  const {
    data: run,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId),
    staleTime: 5_000,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "running" || status === "waiting") return 10_000;
      return false;
    },
  });

  if (isLoading) {
    return (
      <div className={styles.center}>
        <Spinner size="medium" />
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.error}>
        Failed to load run: {(error as Error).message}
      </div>
    );
  }

  if (!run) return null;

  const sortedSteps = [...run.step_results].sort(
    (a, b) => a.execution_order - b.execution_order,
  );

  return (
    <div className={styles.root} style={{ overflowY: "auto", height: "100%" }}>
      {/* Header card */}
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <div>
            <h1 className={styles.title}>{run.workflow_id}</h1>
            <p className={styles.version}>Version {run.workflow_version}</p>
          </div>
          <div className={styles.headerActions}>
            <StatusBadge status={run.status} />
            {TERMINAL_STATUSES.has(run.status) && (
              <Button
                appearance="subtle"
                icon={<DeleteRegular />}
                onClick={() => setConfirmDelete(true)}
                title="Delete run"
                size="small"
              />
            )}
          </div>
        </div>
        <div className={styles.metaGrid}>
          <div>
            <div className={styles.metaLabel}>Run ID</div>
            <div className={styles.metaValue}>
              {runId}
              <CopyButton text={runId} label="Copy run ID" />
            </div>
          </div>
          <div>
            <div className={styles.metaLabel}>Created</div>
            <div className={styles.metaValue}>{timeAgo(run.created_at)}</div>
          </div>
          <div>
            <div className={styles.metaLabel}>Duration</div>
            <div className={styles.metaValue}>
              {formatDuration(run.created_at, run.updated_at)}
            </div>
          </div>
        </div>
      </div>

      <Dialog
        open={confirmDelete}
        onOpenChange={(_, data) => setConfirmDelete(data.open)}
      >
        <DialogSurface>
          <DialogBody>
            <DialogTitle>Delete this run?</DialogTitle>
            <DialogContent>
              This action cannot be undone. The run and all its data will be
              permanently removed.
            </DialogContent>
            <DialogActions>
              <Button
                appearance="secondary"
                onClick={() => setConfirmDelete(false)}
              >
                Cancel
              </Button>
              <Button
                appearance="primary"
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? "Deleting..." : "Delete"}
              </Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>

      {/* Inputs */}
      {run.inputs && Object.keys(run.inputs).length > 0 && (
        <div className={styles.mb6}>
          <button
            onClick={() => setShowInputs(!showInputs)}
            className={styles.sectionToggle}
          >
            {showInputs ? (
              <ChevronDownRegular style={{ width: 14, height: 14 }} />
            ) : (
              <ChevronRightRegular style={{ width: 14, height: 14 }} />
            )}
            Inputs
          </button>
          {showInputs && (
            <div style={{ marginTop: 8 }}>
              <JsonView data={run.inputs} />
            </div>
          )}
        </div>
      )}

      {/* Step timeline */}
      <div className={styles.mb6}>
        <h2 className={styles.sectionTitle}>Step Execution</h2>
        <div className={styles.card}>
          {sortedSteps.length === 0 ? (
            <p className={styles.emptySteps}>No steps executed yet</p>
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
        <div className={styles.mb6}>
          <h2 className={styles.sectionTitle}>Events</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {run.events.map((event, i) => (
              <div key={i} className={styles.eventCard}>
                <div className={styles.eventHeader}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className={styles.eventName}>
                      {event.event_name}
                    </span>
                    {"audience" in event.event_data &&
                      event.event_data.audience != null && (
                        <span className={styles.audienceBadge}>
                          {String(event.event_data.audience)}
                        </span>
                      )}
                  </div>
                  <span
                    style={{
                      fontSize: 12,
                      color: tokens.colorNeutralForeground4,
                    }}
                  >
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
        <div className={styles.mb6}>
          <h2 className={styles.sectionTitle}>Result</h2>
          <div className={styles.card}>
            <JsonView data={run.result} />
          </div>
        </div>
      )}
    </div>
  );
}
