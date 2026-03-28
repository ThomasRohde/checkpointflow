import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { FileCode2, Folder, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import type { WorkflowFile } from "../lib/types";

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

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <FileCode2 className="w-5 h-5 text-zinc-400" />
        <h1 className="text-lg font-semibold text-zinc-900">Workflows</h1>
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

      {workflows && workflows.length > 0 && (
        <div className="space-y-6">
          {Object.entries(groupBySource(workflows)).map(
            ([source, files]) => (
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
                          `/workflows/${encodeURIComponent(wf.path)}`
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
            )
          )}
        </div>
      )}
    </div>
  );
}
