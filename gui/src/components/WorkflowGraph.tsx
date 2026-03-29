import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ReactFlow,
  Background,
  Controls,
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
import { ArrowLeft, Loader2, X } from "lucide-react";
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

function buildGraph(steps: WorkflowStep[]): {
  nodes: StepNodeType[];
  edges: Edge[];
} {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 80, ranksep: 80 });

  const nodes: StepNodeType[] = [];
  const edges: Edge[] = [];
  let colorIdx = 0;

  // Add all nodes
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

  // Helper: add a conditional/branching edge
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

  // Add edges
  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    const nextStep = steps[i + 1];

    // Determine if the step has explicit branching (no implicit fallthrough)
    const hasExplicitBranching =
      step.kind === "end" ||
      step.kind === "switch" ||
      step.kind === "parallel" ||
      (step.transitions && step.transitions.length > 0);

    // Sequential edge to next step (only when no explicit branching)
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

    // await_event transition edges
    if (step.transitions) {
      for (const t of step.transitions) {
        addBranchEdge(step.id, t.next, t.when);
      }
    }

    // switch case edges
    if (step.cases) {
      for (const c of step.cases) {
        addBranchEdge(step.id, c.next, c.when);
      }
      if (step.default) {
        addBranchEdge(step.id, step.default, "default");
      }
    }

    // parallel branch edges
    if (step.branches) {
      for (const b of step.branches) {
        addBranchEdge(step.id, b.start_at, undefined);
      }
    }
  }

  // Layout with dagre
  dagre.layout(g);

  // Apply positions
  for (const node of nodes) {
    const pos = g.node(node.id);
    node.position = {
      x: pos.x - NODE_WIDTH / 2,
      y: pos.y - NODE_HEIGHT / 2,
    };
  }

  return { nodes, edges };
}

function StepDetailPanel({
  step,
  onClose,
}: {
  step: WorkflowStep;
  onClose: () => void;
}) {
  return (
    <div className="absolute top-4 right-4 w-80 bg-white rounded-xl border border-zinc-200 shadow-lg z-10 max-h-[calc(100%-2rem)] overflow-auto">
      <div className="flex items-center justify-between p-4 border-b border-zinc-100">
        <h3 className="text-sm font-semibold text-zinc-900">{step.id}</h3>
        <button
          onClick={onClose}
          className="p-1 hover:bg-zinc-100 rounded-md transition-colors"
        >
          <X className="w-4 h-4 text-zinc-400" />
        </button>
      </div>
      <div className="p-4 space-y-3 text-sm">
        <div>
          <span className="text-xs text-zinc-400">Kind</span>
          <div className="text-zinc-900">{step.kind}</div>
        </div>
        {step.name && (
          <div>
            <span className="text-xs text-zinc-400">Name</span>
            <div className="text-zinc-900">{step.name}</div>
          </div>
        )}
        {step.description && (
          <div>
            <span className="text-xs text-zinc-400">Description</span>
            <div className="text-zinc-700">{step.description}</div>
          </div>
        )}
        {step.command && (
          <div>
            <span className="text-xs text-zinc-400">Command</span>
            <pre className="text-xs font-mono bg-zinc-50 border border-zinc-200 rounded-md p-2 mt-0.5 whitespace-pre-wrap break-all">
              {Array.isArray(step.command)
                ? step.command.join("\n")
                : step.command}
            </pre>
          </div>
        )}
        {step.shell && (
          <div>
            <span className="text-xs text-zinc-400">Shell</span>
            <div className="font-mono text-xs text-zinc-700">{step.shell}</div>
          </div>
        )}
        {step.event_name && (
          <div>
            <span className="text-xs text-zinc-400">Event Name</span>
            <div className="text-zinc-900">{step.event_name}</div>
          </div>
        )}
        {step.if && (
          <div>
            <span className="text-xs text-zinc-400">Condition</span>
            <div className="font-mono text-xs text-zinc-700 italic">
              {step.if}
            </div>
          </div>
        )}
        {step.transitions && step.transitions.length > 0 && (
          <div>
            <span className="text-xs text-zinc-400">Transitions</span>
            <JsonView data={step.transitions} />
          </div>
        )}
        {step.cases && step.cases.length > 0 && (
          <div>
            <span className="text-xs text-zinc-400">Cases</span>
            <JsonView data={step.cases} />
            {step.default && (
              <div className="font-mono text-xs text-zinc-500 mt-1">
                default: {step.default}
              </div>
            )}
          </div>
        )}
        {step.method && step.url && (
          <div>
            <span className="text-xs text-zinc-400">Request</span>
            <div className="font-mono text-xs text-zinc-700">
              {step.method} {step.url}
            </div>
          </div>
        )}
        {step.items && (
          <div>
            <span className="text-xs text-zinc-400">Items</span>
            <div className="font-mono text-xs text-zinc-700">{step.items}</div>
          </div>
        )}
        {step.branches && step.branches.length > 0 && (
          <div>
            <span className="text-xs text-zinc-400">Branches</span>
            <JsonView data={step.branches} />
          </div>
        )}
        {step.workflow_ref && (
          <div>
            <span className="text-xs text-zinc-400">Workflow Ref</span>
            <div className="font-mono text-xs text-zinc-700">
              {step.workflow_ref}
            </div>
          </div>
        )}
        {step.result !== undefined && step.result !== null && (
          <div>
            <span className="text-xs text-zinc-400">Result</span>
            {typeof step.result === "object" ? (
              <JsonView data={step.result} />
            ) : (
              <div className="font-mono text-xs text-zinc-700">
                {String(step.result)}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function WorkflowGraphInner() {
  const [searchParams] = useSearchParams();
  const decodedPath = searchParams.get("path") ?? "";

  const {
    data: workflow,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["workflow", decodedPath],
    queryFn: () => api.getWorkflow(decodedPath),
    enabled: !!decodedPath,
    staleTime: 60_000,
  });

  const { fitView } = useReactFlow();

  const graphData = useMemo(() => {
    if (!workflow?.steps) return null;
    return buildGraph(workflow.steps);
  }, [workflow]);

  const [nodes, setNodes, onNodesChange] = useNodesState<StepNodeType>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedStep, setSelectedStep] = useState<WorkflowStep | null>(null);

  useEffect(() => {
    if (graphData) {
      setNodes(graphData.nodes);
      setEdges(graphData.edges);
      // Fit view after layout is applied
      setTimeout(() => fitView({ padding: 0.2 }), 100);
    }
  }, [graphData, setNodes, setEdges, fitView]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: StepNodeType) => {
      setSelectedStep(node.data.step);
      // Update selection visually
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          data: { ...n.data, selected: n.id === node.id },
        }))
      );
    },
    [setNodes]
  );

  const handleClosePanel = useCallback(() => {
    setSelectedStep(null);
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: { ...n.data, selected: false },
      }))
    );
  }, [setNodes]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-5 h-5 animate-spin text-zinc-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Failed to load workflow: {(error as Error).message}
        </div>
      </div>
    );
  }

  if (!workflow) return null;

  return (
    <div className="h-full flex flex-col">
      {/* Header bar */}
      <div className="flex items-center gap-3 px-5 py-3 border-b border-zinc-200 bg-white shrink-0">
        <Link
          to="/workflows"
          className="p-1 hover:bg-zinc-100 rounded-md transition-colors"
        >
          <ArrowLeft className="w-4 h-4 text-zinc-400" />
        </Link>
        <div>
          <h1 className="text-sm font-semibold text-zinc-900">
            {workflow.name}
          </h1>
          <p className="text-xs text-zinc-400">
            {workflow.id} v{workflow.version}
            {workflow.description ? ` - ${workflow.description}` : ""}
          </p>
        </div>
      </div>

      {/* Graph */}
      <div className="flex-1 relative">
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
          <Controls
            showInteractive={false}
            className="!bg-white !border-zinc-200 !shadow-sm [&>button]:!border-zinc-200 [&>button]:!bg-white [&>button:hover]:!bg-zinc-50"
          />
        </ReactFlow>

        {selectedStep && (
          <StepDetailPanel step={selectedStep} onClose={handleClosePanel} />
        )}
      </div>
    </div>
  );
}

export function WorkflowGraph() {
  return (
    <ReactFlowProvider>
      <WorkflowGraphInner />
    </ReactFlowProvider>
  );
}
