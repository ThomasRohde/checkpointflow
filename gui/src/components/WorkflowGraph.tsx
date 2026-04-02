import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "dagre";
import {
  Button,
  Spinner,
  makeStyles,
  tokens,
} from "@fluentui/react-components";
import {
  ArrowSortRegular,
  DismissRegular,
} from "@fluentui/react-icons";
import { api } from "../lib/api";
import type { WorkflowStep } from "../lib/types";
import { StepNode, type StepNodeData } from "./StepNode";
import { JsonView } from "./JsonView";

type StepNodeType = Node<StepNodeData, "stepNode">;

const nodeTypes = { stepNode: StepNode };

const NODE_WIDTH = 220;
const NODE_HEIGHT = 80;

const transitionColors = [
  "#3b82f6",
  "#8b5cf6",
  "#ec4899",
  "#f97316",
  "#14b8a6",
  "#6366f1",
];

type LayoutDirection = "TB" | "LR";

function buildGraph(
  steps: WorkflowStep[],
  direction: LayoutDirection = "TB",
): {
  nodes: StepNodeType[];
  edges: Edge[];
} {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, nodesep: 80, ranksep: 80 });

  const nodes: StepNodeType[] = [];
  const edges: Edge[] = [];
  let colorIdx = 0;

  for (const step of steps) {
    const id = step.id;
    g.setNode(id, { width: NODE_WIDTH, height: NODE_HEIGHT });
    nodes.push({
      id,
      type: "stepNode",
      position: { x: 0, y: 0 },
      data: { step },
    });
  }

  function addBranchEdge(
    source: string,
    target: string,
    label: string | undefined,
  ) {
    const color = transitionColors[colorIdx % transitionColors.length];
    colorIdx++;
    const edgeId = `br-${source}-${target}-${colorIdx}`;
    g.setEdge(source, target);
    edges.push({
      id: edgeId,
      source,
      target,
      type: "smoothstep",
      animated: true,
      label,
      labelStyle: label ? { fontSize: 10, fill: color } : undefined,
      labelBgStyle: label
        ? { fill: "#fff", fillOpacity: 0.9 }
        : undefined,
      labelBgPadding: label ? ([4, 2] as [number, number]) : undefined,
      labelBgBorderRadius: label ? 4 : undefined,
      style: {
        stroke: color,
        strokeWidth: 1.5,
        strokeDasharray: "6 3",
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color,
        width: 16,
        height: 16,
      },
    });
  }

  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    const nextStep = steps[i + 1];

    const hasExplicitBranching =
      step.kind === "end" ||
      step.kind === "switch" ||
      step.kind === "parallel" ||
      (step.transitions && step.transitions.length > 0);

    if (nextStep && !hasExplicitBranching) {
      const edgeId = `seq-${step.id}-${nextStep.id}`;
      g.setEdge(step.id, nextStep.id);
      edges.push({
        id: edgeId,
        source: step.id,
        target: nextStep.id,
        type: "smoothstep",
        animated: false,
        style: { stroke: "#a1a1aa", strokeWidth: 1.5 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: "#a1a1aa",
          width: 16,
          height: 16,
        },
      });
    }

    if (step.transitions) {
      for (const t of step.transitions) {
        addBranchEdge(step.id, t.next, t.when);
      }
    }

    if (step.cases) {
      for (const c of step.cases) {
        addBranchEdge(step.id, c.next, c.when);
      }
      if (step.default) {
        addBranchEdge(step.id, step.default, "default");
      }
    }

    if (step.branches) {
      for (const b of step.branches) {
        addBranchEdge(step.id, b.start_at, undefined);
      }
    }
  }

  dagre.layout(g);

  for (const node of nodes) {
    const pos = g.node(node.id);
    node.position = {
      x: pos.x - NODE_WIDTH / 2,
      y: pos.y - NODE_HEIGHT / 2,
    };
  }

  return { nodes, edges };
}

const useStyles = makeStyles({
  root: {
    height: "100%",
    display: "flex",
    flexDirection: "column",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    padding: "12px 20px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground1,
    flexShrink: 0,
  },
  headerContent: {
    flex: 1,
    minWidth: 0,
  },
  headerTitle: {
    fontSize: "13px",
    fontWeight: 600,
    color: tokens.colorNeutralForeground1,
    margin: 0,
  },
  headerSub: {
    fontSize: "12px",
    color: tokens.colorNeutralForeground4,
    margin: 0,
  },
  graph: {
    flex: 1,
    position: "relative",
  },
  detailPanel: {
    position: "absolute",
    top: "16px",
    right: "16px",
    width: "320px",
    backgroundColor: tokens.colorNeutralBackground1,
    borderRadius: "12px",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    boxShadow: tokens.shadow16,
    zIndex: 10,
    maxHeight: "calc(100% - 32px)",
    overflowY: "auto",
  },
  detailHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "16px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
  },
  detailTitle: {
    fontSize: "13px",
    fontWeight: 600,
    color: tokens.colorNeutralForeground1,
  },
  detailBody: {
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    fontSize: "13px",
  },
  detailLabel: {
    fontSize: "12px",
    color: tokens.colorNeutralForeground4,
  },
  detailValue: {
    color: tokens.colorNeutralForeground1,
  },
  detailMono: {
    fontFamily: "monospace",
    fontSize: "12px",
    color: tokens.colorNeutralForeground2,
  },
  detailPre: {
    fontSize: "12px",
    fontFamily: "monospace",
    backgroundColor: tokens.colorNeutralBackground3,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: "6px",
    padding: "8px",
    marginTop: "2px",
    whiteSpace: "pre-wrap",
    wordBreak: "break-all",
  },
  center: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    height: "100%",
  },
  error: {
    padding: "16px",
    margin: "24px",
    borderRadius: "8px",
    border: `1px solid ${tokens.colorPaletteRedBorder2}`,
    backgroundColor: tokens.colorPaletteRedBackground1,
    color: tokens.colorPaletteRedForeground1,
    fontSize: "13px",
  },
});

function StepDetailPanel({
  step,
  onClose,
}: {
  step: WorkflowStep;
  onClose: () => void;
}) {
  const styles = useStyles();

  return (
    <div className={styles.detailPanel}>
      <div className={styles.detailHeader}>
        <span className={styles.detailTitle}>{step.id}</span>
        <Button
          appearance="subtle"
          icon={<DismissRegular />}
          onClick={onClose}
          size="small"
        />
      </div>
      <div className={styles.detailBody}>
        <div>
          <span className={styles.detailLabel}>Kind</span>
          <div className={styles.detailValue}>{step.kind}</div>
        </div>
        {step.name && (
          <div>
            <span className={styles.detailLabel}>Name</span>
            <div className={styles.detailValue}>{step.name}</div>
          </div>
        )}
        {step.description && (
          <div>
            <span className={styles.detailLabel}>Description</span>
            <div className={styles.detailValue}>{step.description}</div>
          </div>
        )}
        {step.command && (
          <div>
            <span className={styles.detailLabel}>Command</span>
            <pre className={styles.detailPre}>
              {Array.isArray(step.command)
                ? step.command.join("\n")
                : step.command}
            </pre>
          </div>
        )}
        {step.shell && (
          <div>
            <span className={styles.detailLabel}>Shell</span>
            <div className={styles.detailMono}>{step.shell}</div>
          </div>
        )}
        {step.event_name && (
          <div>
            <span className={styles.detailLabel}>Event Name</span>
            <div className={styles.detailValue}>{step.event_name}</div>
          </div>
        )}
        {step.if && (
          <div>
            <span className={styles.detailLabel}>Condition</span>
            <div className={styles.detailMono} style={{ fontStyle: "italic" }}>
              {step.if}
            </div>
          </div>
        )}
        {step.transitions && step.transitions.length > 0 && (
          <div>
            <span className={styles.detailLabel}>Transitions</span>
            <JsonView data={step.transitions} />
          </div>
        )}
        {step.cases && step.cases.length > 0 && (
          <div>
            <span className={styles.detailLabel}>Cases</span>
            <JsonView data={step.cases} />
            {step.default && (
              <div className={styles.detailMono} style={{ marginTop: 4 }}>
                default: {step.default}
              </div>
            )}
          </div>
        )}
        {step.method && step.url && (
          <div>
            <span className={styles.detailLabel}>Request</span>
            <div className={styles.detailMono}>
              {step.method} {step.url}
            </div>
          </div>
        )}
        {step.items && (
          <div>
            <span className={styles.detailLabel}>Items</span>
            <div className={styles.detailMono}>{step.items}</div>
          </div>
        )}
        {step.branches && step.branches.length > 0 && (
          <div>
            <span className={styles.detailLabel}>Branches</span>
            <JsonView data={step.branches} />
          </div>
        )}
        {step.workflow_ref && (
          <div>
            <span className={styles.detailLabel}>Workflow Ref</span>
            <div className={styles.detailMono}>{step.workflow_ref}</div>
          </div>
        )}
        {step.result !== undefined && step.result !== null && (
          <div>
            <span className={styles.detailLabel}>Result</span>
            {typeof step.result === "object" ? (
              <JsonView data={step.result} />
            ) : (
              <div className={styles.detailMono}>{String(step.result)}</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function WorkflowGraphInner({ workflowPath }: { workflowPath: string }) {
  const styles = useStyles();

  const {
    data: workflow,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["workflow", workflowPath],
    queryFn: () => api.getWorkflow(workflowPath),
    enabled: !!workflowPath,
    staleTime: 60_000,
  });

  const { fitView } = useReactFlow();
  const [direction, setDirection] = useState<LayoutDirection>("TB");

  const graphData = useMemo(() => {
    if (!workflow?.steps) return null;
    return buildGraph(workflow.steps, direction);
  }, [workflow, direction]);

  const [nodes, setNodes, onNodesChange] = useNodesState<StepNodeType>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedStep, setSelectedStep] = useState<WorkflowStep | null>(null);

  useEffect(() => {
    if (graphData) {
      setNodes(graphData.nodes);
      setEdges(graphData.edges);
      setTimeout(() => fitView({ padding: 0.2 }), 100);
    }
  }, [graphData, setNodes, setEdges, fitView]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: StepNodeType) => {
      setSelectedStep(node.data.step);
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          data: { ...n.data, selected: n.id === node.id },
        })),
      );
    },
    [setNodes],
  );

  const handleClosePanel = useCallback(() => {
    setSelectedStep(null);
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: { ...n.data, selected: false },
      })),
    );
  }, [setNodes]);

  if (isLoading) {
    return (
      <div className={styles.center}>
        <Spinner size="medium" />
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.error}>
        Failed to load workflow: {(error as Error).message}
      </div>
    );
  }

  if (!workflow) return null;

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <div className={styles.headerContent}>
          <h1 className={styles.headerTitle}>{workflow.name}</h1>
          <p className={styles.headerSub}>
            {workflow.id} v{workflow.version}
            {workflow.description ? ` — ${workflow.description}` : ""}
          </p>
        </div>
        <Button
          appearance="subtle"
          size="small"
          icon={<ArrowSortRegular />}
          onClick={() => setDirection((d) => (d === "TB" ? "LR" : "TB"))}
          title={
            direction === "TB"
              ? "Switch to horizontal layout"
              : "Switch to vertical layout"
          }
        >
          {direction === "TB" ? "Horizontal" : "Vertical"}
        </Button>
      </div>

      <div className={styles.graph}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.3}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#e4e4e7" gap={20} size={1} />
          <Controls showInteractive={false} />
          <MiniMap nodeColor="#d4d4d8" maskColor="rgba(250, 250, 250, 0.7)" />
        </ReactFlow>

        {selectedStep && (
          <StepDetailPanel step={selectedStep} onClose={handleClosePanel} />
        )}
      </div>
    </div>
  );
}

export function WorkflowGraph({ workflowPath }: { workflowPath: string }) {
  return (
    <ReactFlowProvider>
      <WorkflowGraphInner workflowPath={workflowPath} />
    </ReactFlowProvider>
  );
}
