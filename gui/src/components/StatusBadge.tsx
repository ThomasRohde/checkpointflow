import { Badge } from "@fluentui/react-components";
import type { RunStatus } from "../lib/types";

const colorMap: Record<
  RunStatus,
  "success" | "brand" | "warning" | "danger" | "informative"
> = {
  completed: "success",
  running: "brand",
  waiting: "warning",
  failed: "danger",
  cancelled: "informative",
};

export function StatusBadge({ status }: { status: RunStatus }) {
  return (
    <Badge appearance="filled" color={colorMap[status] ?? "informative"}>
      {status}
    </Badge>
  );
}
