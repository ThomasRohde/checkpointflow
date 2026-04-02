import type { IDockviewPanelProps } from "dockview";
import { RunDetail } from "../components/RunDetail";

export function RunDetailPanel(
  props: IDockviewPanelProps<{ runId: string }>,
) {
  return <RunDetail runId={props.params.runId} panelApi={props.api} />;
}
