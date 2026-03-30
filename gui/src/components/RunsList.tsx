import { useCallback, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Activity, ArrowDown, ArrowUp, Loader2, Search, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import type { RunSummary } from "../lib/types";
import { StatusBadge } from "./StatusBadge";
import { timeAgo } from "../lib/utils";

type SortKey = "workflow_id" | "status" | "current_step_id" | "created_at" | "updated_at";
type SortDir = "asc" | "desc";

function comparator(key: SortKey, dir: SortDir) {
  return (a: RunSummary, b: RunSummary) => {
    const va = a[key] ?? "";
    const vb = b[key] ?? "";
    const cmp = va < vb ? -1 : va > vb ? 1 : 0;
    return dir === "asc" ? cmp : -cmp;
  };
}

function SortHeader({
  label,
  sortKey,
  activeKey,
  dir,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  activeKey: SortKey;
  dir: SortDir;
  onSort: (key: SortKey) => void;
}) {
  const active = sortKey === activeKey;
  return (
    <th
      className="text-left px-4 py-3 font-medium text-zinc-500 cursor-pointer select-none hover:text-zinc-700 transition-colors"
      onClick={() => onSort(sortKey)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {active &&
          (dir === "asc" ? (
            <ArrowUp className="w-3 h-3" />
          ) : (
            <ArrowDown className="w-3 h-3" />
          ))}
      </span>
    </th>
  );
}

export function RunsList() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: runs, isLoading, error } = useQuery({
    queryKey: ["runs"],
    queryFn: api.getRuns,
    staleTime: 30_000,
  });

  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "created_at" || key === "updated_at" ? "desc" : "asc");
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
          (r.current_step_id ?? "").toLowerCase().includes(q)
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
    const confirmed = window.confirm(
      `Delete ${selected.size} run${selected.size > 1 ? "s" : ""}?`
    );
    if (!confirmed) return;
    setDeleting(true);
    try {
      await api.bulkDeleteRuns([...selected]);
      setSelected(new Set());
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    } finally {
      setDeleting(false);
    }
  }, [selected, queryClient]);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Activity className="w-5 h-5 text-zinc-400" />
          <h1 className="text-lg font-semibold text-zinc-900">Runs</h1>
        </div>
        <div className="flex items-center gap-3">
          {selected.size > 0 && (
            <button
              onClick={handleBulkDelete}
              disabled={deleting}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-red-700 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 disabled:opacity-50 transition-colors"
            >
              {deleting ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Trash2 className="w-3.5 h-3.5" />
              )}
              Delete {selected.size}
            </button>
          )}
          {runs && runs.length > 0 && (
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
              <input
                type="text"
                placeholder="Search runs..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 pr-3 py-1.5 text-sm rounded-lg border border-zinc-200 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-300 w-64 transition-colors"
              />
            </div>
          )}
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-5 h-5 animate-spin text-zinc-400" />
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Failed to load runs: {(error as Error).message}
        </div>
      )}

      {runs && runs.length === 0 && (
        <div className="text-center py-20 text-zinc-400">
          <Activity className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="text-sm">No runs found</p>
        </div>
      )}

      {runs && runs.length > 0 && filtered.length === 0 && (
        <div className="text-center py-20 text-zinc-400">
          <Search className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="text-sm">No runs match "{search}"</p>
        </div>
      )}

      {filtered.length > 0 && (
        <div className="bg-white rounded-xl border border-zinc-200 overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-100 bg-zinc-50/50">
                <th className="w-10 px-3 py-3">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleAll}
                    className="rounded border-zinc-300 text-blue-600 focus:ring-blue-500/20"
                  />
                </th>
                <SortHeader label="Workflow" sortKey="workflow_id" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortHeader label="Status" sortKey="status" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortHeader label="Current Step" sortKey="current_step_id" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortHeader label="Created" sortKey="created_at" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortHeader label="Updated" sortKey="updated_at" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
              </tr>
            </thead>
            <tbody>
              {filtered.map((run) => (
                <tr
                  key={run.run_id}
                  onClick={() => navigate(`/runs/${run.run_id}`)}
                  className="border-b border-zinc-50 hover:bg-zinc-50 cursor-pointer transition-colors"
                >
                  <td className="w-10 px-3 py-3" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selected.has(run.run_id)}
                      onChange={() => toggleOne(run.run_id)}
                      className="rounded border-zinc-300 text-blue-600 focus:ring-blue-500/20"
                    />
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-zinc-900">
                      {run.workflow_id}
                    </div>
                    <div className="text-xs text-zinc-400 font-mono">
                      {run.run_id.slice(0, 8)}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-3 text-zinc-600 font-mono text-xs">
                    {run.current_step_id ?? "-"}
                  </td>
                  <td className="px-4 py-3 text-zinc-500 text-xs">
                    {timeAgo(run.created_at)}
                  </td>
                  <td className="px-4 py-3 text-zinc-500 text-xs">
                    {timeAgo(run.updated_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
