import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  ArrowDown,
  ArrowUp,
  FileCode2,
  Folder,
  Loader2,
  Search,
} from "lucide-react";
import { api } from "../lib/api";
import type { WorkflowFile } from "../lib/types";

type SortKey = "name" | "relative" | "source";
type SortDir = "asc" | "desc";

function groupBySource(
  workflows: WorkflowFile[]
): Record<string, WorkflowFile[]> {
  const groups: Record<string, WorkflowFile[]> = {};
  for (const wf of workflows) {
    const key = wf.source || "other";
    if (!groups[key]) groups[key] = [];
    groups[key].push(wf);
  }
  return groups;
}

const sourceLabels: Record<string, string> = {
  cwd: "Current Directory",
  home: "Home Directory",
};

export function WorkflowsList() {
  const navigate = useNavigate();
  const {
    data: workflows,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["workflows"],
    queryFn: api.getWorkflows,
    staleTime: 30_000,
  });

  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const filtered = useMemo(() => {
    if (!workflows) return [];
    const q = search.toLowerCase().trim();
    let result = workflows;
    if (q) {
      result = workflows.filter(
        (wf) =>
          wf.name.toLowerCase().includes(q) ||
          wf.relative.toLowerCase().includes(q) ||
          wf.path.toLowerCase().includes(q)
      );
    }
    return [...result].sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      const cmp = va.localeCompare(vb);
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [workflows, search, sortKey, sortDir]);

  const groups = useMemo(() => groupBySource(filtered), [filtered]);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <FileCode2 className="w-5 h-5 text-zinc-400" />
          <h1 className="text-lg font-semibold text-zinc-900">Workflows</h1>
        </div>
        {workflows && workflows.length > 0 && (
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
              <input
                type="text"
                placeholder="Search workflows..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 pr-3 py-1.5 text-sm rounded-lg border border-zinc-200 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-300 w-56 transition-colors"
              />
            </div>
            <div className="flex items-center gap-1 text-xs text-zinc-500">
              {(["name", "path"] as const).map((key) => {
                const k: SortKey = key === "path" ? "relative" : key;
                const active = sortKey === k;
                return (
                  <button
                    key={key}
                    onClick={() => handleSort(k)}
                    className={`px-2 py-1 rounded transition-colors ${active ? "bg-zinc-200 text-zinc-700" : "hover:bg-zinc-100"}`}
                  >
                    <span className="inline-flex items-center gap-0.5">
                      {key === "path" ? "Path" : "Name"}
                      {active &&
                        (sortDir === "asc" ? (
                          <ArrowUp className="w-3 h-3" />
                        ) : (
                          <ArrowDown className="w-3 h-3" />
                        ))}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-5 h-5 animate-spin text-zinc-400" />
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Failed to load workflows: {(error as Error).message}
        </div>
      )}

      {workflows && workflows.length === 0 && (
        <div className="text-center py-20 text-zinc-400">
          <FileCode2 className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="text-sm">No workflows found</p>
        </div>
      )}

      {workflows && workflows.length > 0 && filtered.length === 0 && (
        <div className="text-center py-20 text-zinc-400">
          <Search className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="text-sm">No workflows match "{search}"</p>
        </div>
      )}

      {filtered.length > 0 && (
        <div className="space-y-6">
          {Object.entries(groups).map(([source, files]) => (
            <div key={source}>
              <div className="flex items-center gap-2 mb-3">
                <Folder className="w-4 h-4 text-zinc-400" />
                <h2 className="text-sm font-medium text-zinc-500">
                  {sourceLabels[source] ?? source}
                </h2>
              </div>
              <div className="space-y-1">
                {files.map((wf) => (
                  <button
                    key={wf.path}
                    onClick={() =>
                      navigate(
                        `/workflows/view?path=${encodeURIComponent(wf.path)}`
                      )
                    }
                    className="w-full flex items-center gap-3 px-4 py-3 bg-white rounded-lg border border-zinc-200 hover:border-zinc-300 hover:shadow-sm transition-all text-left group"
                  >
                    <FileCode2 className="w-4 h-4 text-zinc-400 group-hover:text-blue-500 transition-colors" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-zinc-900 truncate">
                        {wf.name}
                      </div>
                      <div className="text-xs text-zinc-400 font-mono truncate">
                        {wf.relative}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
