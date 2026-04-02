import { useCallback, useMemo, useState, useContext } from "react";
import { useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import {
  Button,
  Input,
  Checkbox,
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
  ArrowSortUpRegular,
  ArrowSortDownRegular,
  DeleteRegular,
  SearchRegular,
  ChevronLeftRegular,
  ChevronRightRegular,
} from "@fluentui/react-icons";
import { Activity } from "lucide-react";
import { api } from "../lib/api";
import type { PaginatedRuns, RunSummary } from "../lib/types";
import { StatusBadge } from "./StatusBadge";
import { CopyButton } from "./CopyButton";
import { timeAgo } from "../lib/utils";
import { usePanelNavigation } from "../hooks/usePanelNavigation";
import { ToasterContext } from "../App";

type SortKey =
  | "workflow_id"
  | "status"
  | "current_step_id"
  | "created_at"
  | "updated_at";
type SortDir = "asc" | "desc";

const PER_PAGE = 50;

function comparator(key: SortKey, dir: SortDir) {
  return (a: RunSummary, b: RunSummary) => {
    const va = a[key] ?? "";
    const vb = b[key] ?? "";
    const cmp = va < vb ? -1 : va > vb ? 1 : 0;
    return dir === "asc" ? cmp : -cmp;
  };
}

const useStyles = makeStyles({
  root: {
    padding: "24px",
    maxWidth: "1200px",
    marginLeft: "auto",
    marginRight: "auto",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: "24px",
  },
  titleGroup: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  title: {
    fontSize: "18px",
    fontWeight: 600,
    color: tokens.colorNeutralForeground1,
    margin: 0,
  },
  total: {
    fontSize: "12px",
    color: tokens.colorNeutralForeground4,
  },
  actions: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "13px",
    backgroundColor: tokens.colorNeutralBackground1,
    borderRadius: "8px",
    overflow: "hidden",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  th: {
    textAlign: "left",
    padding: "12px 16px",
    fontWeight: 500,
    color: tokens.colorNeutralForeground3,
    cursor: "pointer",
    userSelect: "none",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground2,
    "&:hover": {
      color: tokens.colorNeutralForeground1,
    },
  },
  thContent: {
    display: "inline-flex",
    alignItems: "center",
    gap: "4px",
  },
  checkboxTh: {
    width: "40px",
    padding: "12px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground2,
  },
  row: {
    cursor: "pointer",
    borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
    "&:hover": {
      backgroundColor: tokens.colorNeutralBackground1Hover,
    },
  },
  td: {
    padding: "12px 16px",
  },
  checkboxTd: {
    width: "40px",
    padding: "12px",
  },
  workflowName: {
    fontWeight: 500,
    color: tokens.colorNeutralForeground1,
  },
  runId: {
    display: "flex",
    alignItems: "center",
    gap: "2px",
    fontSize: "11px",
    color: tokens.colorNeutralForeground4,
    fontFamily: "monospace",
  },
  mono: {
    fontFamily: "monospace",
    fontSize: "12px",
    color: tokens.colorNeutralForeground3,
  },
  time: {
    fontSize: "12px",
    color: tokens.colorNeutralForeground3,
  },
  center: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "80px 0",
  },
  empty: {
    textAlign: "center",
    padding: "80px 0",
    color: tokens.colorNeutralForeground4,
  },
  emptyIcon: {
    width: "40px",
    height: "40px",
    margin: "0 auto 12px",
    opacity: 0.4,
  },
  error: {
    padding: "16px",
    borderRadius: "8px",
    border: `1px solid ${tokens.colorPaletteRedBorder2}`,
    backgroundColor: tokens.colorPaletteRedBackground1,
    color: tokens.colorPaletteRedForeground1,
    fontSize: "13px",
  },
  pagination: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: "16px",
  },
  pageInfo: {
    fontSize: "12px",
    color: tokens.colorNeutralForeground4,
  },
  pageButtons: {
    display: "flex",
    alignItems: "center",
    gap: "4px",
  },
});

export function RunsList() {
  const { openRunDetail } = usePanelNavigation();
  const queryClient = useQueryClient();
  const toastController = useContext(ToasterContext);
  const styles = useStyles();
  const [page, setPage] = useState(1);

  const {
    data: response,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["runs", page],
    queryFn: () => api.getRuns(page, PER_PAGE),
    staleTime: 30_000,
  });

  const runs = response?.runs;
  const total = response?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const [confirmBulkDelete, setConfirmBulkDelete] = useState(false);

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(
        key === "created_at" || key === "updated_at" ? "desc" : "asc",
      );
    }
  };

  const filtered = useMemo(() => {
    if (!runs) return [];
    const q = search.toLowerCase().trim();
    let result = runs;
    if (q) {
      result = runs.filter(
        (r) =>
          r.workflow_id.toLowerCase().includes(q) ||
          r.run_id.toLowerCase().includes(q) ||
          r.status.toLowerCase().includes(q) ||
          (r.current_step_id ?? "").toLowerCase().includes(q),
      );
    }
    return [...result].sort(comparator(sortKey, sortDir));
  }, [runs, search, sortKey, sortDir]);

  const allSelected =
    filtered.length > 0 && filtered.every((r) => selected.has(r.run_id));

  const toggleAll = useCallback(() => {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(filtered.map((r) => r.run_id)));
    }
  }, [filtered, allSelected]);

  const toggleOne = useCallback((runId: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(runId)) next.delete(runId);
      else next.add(runId);
      return next;
    });
  }, []);

  const handleBulkDelete = useCallback(async () => {
    if (selected.size === 0) return;
    setDeleting(true);

    const queryKey: QueryKey = ["runs", page];
    const previous = queryClient.getQueryData<PaginatedRuns>(queryKey);
    if (previous) {
      queryClient.setQueryData<PaginatedRuns>(queryKey, {
        ...previous,
        runs: previous.runs.filter((r) => !selected.has(r.run_id)),
        total: previous.total - selected.size,
      });
    }

    try {
      const result = await api.bulkDeleteRuns([...selected]);
      const count = result.deleted.length;
      toastController?.dispatchToast(
        <Toast>
          <ToastBody>
            Deleted {count} run{count !== 1 ? "s" : ""}
          </ToastBody>
        </Toast>,
        { intent: "success" },
      );
      setSelected(new Set());
      setConfirmBulkDelete(false);
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    } catch (err) {
      if (previous) queryClient.setQueryData(queryKey, previous);
      toastController?.dispatchToast(
        <Toast>
          <ToastBody>Delete failed: {(err as Error).message}</ToastBody>
        </Toast>,
        { intent: "error" },
      );
    } finally {
      setDeleting(false);
    }
  }, [selected, queryClient, page, toastController]);

  const SortIcon = sortDir === "asc" ? ArrowSortUpRegular : ArrowSortDownRegular;

  function SortHeader({ label, k }: { label: string; k: SortKey }) {
    return (
      <th className={styles.th} onClick={() => handleSort(k)}>
        <span className={styles.thContent}>
          {label}
          {sortKey === k && <SortIcon style={{ width: 12, height: 12 }} />}
        </span>
      </th>
    );
  }

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <div className={styles.titleGroup}>
          <Activity style={{ width: 20, height: 20, color: "#a1a1aa" }} />
          <h1 className={styles.title}>Runs</h1>
          {total > 0 && <span className={styles.total}>{total} total</span>}
        </div>
        <div className={styles.actions}>
          {selected.size > 0 && (
            <Button
              appearance="primary"
              icon={<DeleteRegular />}
              onClick={() => setConfirmBulkDelete(true)}
              size="small"
            >
              Delete {selected.size}
            </Button>
          )}
          {runs && runs.length > 0 && (
            <Input
              contentBefore={<SearchRegular />}
              placeholder="Search runs..."
              value={search}
              onChange={(_, data) => setSearch(data.value)}
              size="small"
              style={{ width: 240 }}
            />
          )}
        </div>
      </div>

      <Dialog
        open={confirmBulkDelete}
        onOpenChange={(_, data) => setConfirmBulkDelete(data.open)}
      >
        <DialogSurface>
          <DialogBody>
            <DialogTitle>Delete {selected.size} runs?</DialogTitle>
            <DialogContent>
              This action cannot be undone. The selected runs and their data will
              be permanently removed.
            </DialogContent>
            <DialogActions>
              <Button
                appearance="secondary"
                onClick={() => setConfirmBulkDelete(false)}
              >
                Cancel
              </Button>
              <Button
                appearance="primary"
                onClick={handleBulkDelete}
                disabled={deleting}
                icon={deleting ? <Spinner size="tiny" /> : undefined}
              >
                {deleting ? "Deleting..." : "Delete"}
              </Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>

      {isLoading && (
        <div className={styles.center}>
          <Spinner size="medium" />
        </div>
      )}

      {error && (
        <div className={styles.error}>
          Failed to load runs: {(error as Error).message}
        </div>
      )}

      {runs && runs.length === 0 && total === 0 && (
        <div className={styles.empty}>
          <Activity className={styles.emptyIcon} />
          <p>No runs found</p>
        </div>
      )}

      {filtered.length > 0 && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.checkboxTh}>
                <Checkbox
                  checked={allSelected ? true : selected.size > 0 ? "mixed" : false}
                  onChange={toggleAll}
                  aria-label="Select all runs"
                />
              </th>
              <SortHeader label="Workflow" k="workflow_id" />
              <SortHeader label="Status" k="status" />
              <SortHeader label="Current Step" k="current_step_id" />
              <SortHeader label="Created" k="created_at" />
              <SortHeader label="Updated" k="updated_at" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((run) => (
              <tr
                key={run.run_id}
                className={styles.row}
                onClick={() => openRunDetail(run.run_id, run.workflow_id)}
              >
                <td
                  className={styles.checkboxTd}
                  onClick={(e) => e.stopPropagation()}
                >
                  <Checkbox
                    checked={selected.has(run.run_id)}
                    onChange={() => toggleOne(run.run_id)}
                    aria-label={`Select run ${run.run_id.slice(0, 8)}`}
                  />
                </td>
                <td className={styles.td}>
                  <div className={styles.workflowName}>{run.workflow_id}</div>
                  <div className={styles.runId}>
                    <span title={run.run_id}>{run.run_id.slice(0, 12)}</span>
                    <CopyButton text={run.run_id} label="Copy run ID" />
                  </div>
                </td>
                <td className={styles.td}>
                  <StatusBadge status={run.status} />
                </td>
                <td className={`${styles.td} ${styles.mono}`}>
                  {run.current_step_id ?? "-"}
                </td>
                <td className={`${styles.td} ${styles.time}`}>
                  {timeAgo(run.created_at)}
                </td>
                <td className={`${styles.td} ${styles.time}`}>
                  {timeAgo(run.updated_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {totalPages > 1 && (
        <div className={styles.pagination}>
          <span className={styles.pageInfo}>
            Page {page} of {totalPages}
          </span>
          <div className={styles.pageButtons}>
            <Button
              appearance="subtle"
              icon={<ChevronLeftRegular />}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              size="small"
              aria-label="Previous page"
            />
            <Button
              appearance="subtle"
              icon={<ChevronRightRegular />}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              size="small"
              aria-label="Next page"
            />
          </div>
        </div>
      )}
    </div>
  );
}
