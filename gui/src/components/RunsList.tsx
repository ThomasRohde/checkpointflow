import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Activity, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { StatusBadge } from "./StatusBadge";
import { timeAgo } from "../lib/utils";

export function RunsList() {
  const navigate = useNavigate();
  const { data: runs, isLoading, error } = useQuery({
    queryKey: ["runs"],
    queryFn: api.getRuns,
    staleTime: 30_000,
  });

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Activity className="w-5 h-5 text-zinc-400" />
        <h1 className="text-lg font-semibold text-zinc-900">Runs</h1>
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

      {runs && runs.length > 0 && (
        <div className="bg-white rounded-xl border border-zinc-200 overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-100 bg-zinc-50/50">
                <th className="text-left px-4 py-3 font-medium text-zinc-500">
                  Workflow
                </th>
                <th className="text-left px-4 py-3 font-medium text-zinc-500">
                  Status
                </th>
                <th className="text-left px-4 py-3 font-medium text-zinc-500">
                  Current Step
                </th>
                <th className="text-left px-4 py-3 font-medium text-zinc-500">
                  Created
                </th>
                <th className="text-left px-4 py-3 font-medium text-zinc-500">
                  Updated
                </th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.run_id}
                  onClick={() => navigate(`/runs/${run.run_id}`)}
                  className="border-b border-zinc-50 hover:bg-zinc-50 cursor-pointer transition-colors"
                >
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
