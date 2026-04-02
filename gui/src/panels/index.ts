import type { IDockviewPanelProps } from "dockview";
import { RunsListPanel } from "./RunsListPanel";
import { RunDetailPanel } from "./RunDetailPanel";
import { WorkflowsListPanel } from "./WorkflowsListPanel";
import { WorkflowGraphPanel } from "./WorkflowGraphPanel";

export const panelComponents: Record<
  string,
  React.FunctionComponent<IDockviewPanelProps>
> = {
  "runs-list": RunsListPanel,
  "run-detail": RunDetailPanel as React.FunctionComponent<IDockviewPanelProps>,
  "workflows-list": WorkflowsListPanel,
  "workflow-graph": WorkflowGraphPanel as React.FunctionComponent<IDockviewPanelProps>,
};
