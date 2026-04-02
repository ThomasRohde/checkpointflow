import type { IDockviewPanelProps } from "dockview";
import { WorkflowGraph } from "../components/WorkflowGraph";

export function WorkflowGraphPanel(
  props: IDockviewPanelProps<{ path: string }>,
) {
  return <WorkflowGraph workflowPath={props.params.path} />;
}
