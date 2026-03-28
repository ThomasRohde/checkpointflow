import { cn } from "../lib/utils";
import type { RunStatus } from "../lib/types";

const statusStyles: Record<RunStatus, string> = {
  completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  running: "bg-blue-50 text-blue-700 border-blue-200",
  waiting: "bg-amber-50 text-amber-700 border-amber-200",
  failed: "bg-red-50 text-red-700 border-red-200",
  cancelled: "bg-zinc-100 text-zinc-500 border-zinc-200",
};

const statusDot: Record<RunStatus, string> = {
  completed: "bg-emerald-500",
  running: "bg-blue-500",
  waiting: "bg-amber-500",
  failed: "bg-red-500",
  cancelled: "bg-zinc-400",
};

export function StatusBadge({
  status,
  className,
}: {
  status: RunStatus;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border",
        statusStyles[status] ?? "bg-zinc-100 text-zinc-500 border-zinc-200",
        className
      )}
    >
      <span
        className={cn(
          "w-1.5 h-1.5 rounded-full",
          statusDot[status] ?? "bg-zinc-400"
        )}
      />
      {status}
    </span>
  );
}
