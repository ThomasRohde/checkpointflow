import { useContext } from "react";
import { DockviewApiContext } from "../App";

export function usePanelNavigation() {
  const api = useContext(DockviewApiContext);

  function openRunDetail(runId: string, title: string) {
    if (!api) return;
    const panelId = `run-${runId}`;
    const existing = api.getPanel(panelId);
    if (existing) {
      existing.api.setActive();
      return;
    }
    api.addPanel({
      id: panelId,
      component: "run-detail",
      title,
      tabComponent: "closable",
      params: { runId },
    });
  }

  function openWorkflowGraph(path: string, name: string) {
    if (!api) return;
    const panelId = `wf-${path}`;
    const existing = api.getPanel(panelId);
    if (existing) {
      existing.api.setActive();
      return;
    }
    api.addPanel({
      id: panelId,
      component: "workflow-graph",
      title: name,
      tabComponent: "closable",
      params: { path },
    });
  }

  return { openRunDetail, openWorkflowGraph, api };
}
