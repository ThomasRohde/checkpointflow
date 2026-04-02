import { memo } from "react";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import {
  Terminal,
  Pause,
  Flag,
  Circle,
  GitBranch,
  Globe,
  Repeat,
  Columns3,
  Workflow,
} from "lucide-react";
import type { WorkflowStep } from "../lib/types";
import { truncate } from "../lib/utils";

export type StepNodeData = {
  step: WorkflowStep;
  selected?: boolean;
};

type StepNodeType = Node<StepNodeData, "stepNode">;

const kindConfig: Record<
  string,
  {
    icon: React.ElementType;
    bg: string;
    border: string;
    text: string;
    radius: string;
  }
> = {
  cli: {
    icon: Terminal,
    bg: "#eff6ff",
    border: "#93c5fd",
    text: "#1e40af",
    radius: "8px",
  },
  await_event: {
    icon: Pause,
    bg: "#fffbeb",
    border: "#fcd34d",
    text: "#92400e",
    radius: "12px",
  },
  end: {
    icon: Flag,
    bg: "#ecfdf5",
    border: "#6ee7b7",
    text: "#065f46",
    radius: "9999px",
  },
  switch: {
    icon: GitBranch,
    bg: "#f5f3ff",
    border: "#c4b5fd",
    text: "#5b21b6",
    radius: "8px",
  },
  api: {
    icon: Globe,
    bg: "#ecfeff",
    border: "#67e8f9",
    text: "#155e75",
    radius: "8px",
  },
  foreach: {
    icon: Repeat,
    bg: "#fff1f2",
    border: "#fda4af",
    text: "#9f1239",
    radius: "8px",
  },
  parallel: {
    icon: Columns3,
    bg: "#eef2ff",
    border: "#a5b4fc",
    text: "#3730a3",
    radius: "8px",
  },
  workflow: {
    icon: Workflow,
    bg: "#f0fdfa",
    border: "#5eead4",
    text: "#134e4a",
    radius: "8px",
  },
};

const defaultConfig = {
  icon: Circle,
  bg: "#fafafa",
  border: "#d4d4d8",
  text: "#52525b",
  radius: "8px",
};

function StepNodeComponent({ data }: NodeProps<StepNodeType>) {
  const { step } = data;
  const config = kindConfig[step.kind] ?? defaultConfig;
  const Icon = config.icon;

  const isEnd = step.kind === "end";
  const subtitle =
    step.kind === "cli" && step.command
      ? truncate(
          Array.isArray(step.command) ? step.command.join(" && ") : step.command,
          40,
        )
      : step.kind === "await_event" && step.event_name
        ? step.event_name
        : step.kind === "api" && step.method && step.url
          ? truncate(`${step.method} ${step.url}`, 40)
          : step.kind === "foreach" && step.items
            ? `over ${step.items}`
            : step.kind === "parallel" && step.branches
              ? `${step.branches.length} branches`
              : step.kind === "workflow" && step.workflow_ref
                ? truncate(step.workflow_ref, 40)
                : step.kind === "switch" && step.cases
                  ? `${step.cases.length} cases`
                  : step.description
                    ? truncate(step.description, 40)
                    : null;

  return (
    <>
      <Handle
        type="target"
        position={Position.Top}
        style={{
          background: "#d4d4d8",
          width: 8,
          height: 8,
          border: "none",
        }}
      />
      <div
        style={{
          borderWidth: 2,
          borderStyle: "solid",
          borderColor: config.border,
          backgroundColor: config.bg,
          borderRadius: config.radius,
          padding: "12px 16px",
          boxShadow: data.selected
            ? "0 0 0 3px #2563eb, 0 0 0 5px rgba(37,99,235,0.2)"
            : "0 1px 2px rgba(0,0,0,0.05)",
          minWidth: isEnd ? 80 : 180,
          maxWidth: 260,
          textAlign: isEnd ? "center" : "left",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <Icon
            style={{
              width: 16,
              height: 16,
              flexShrink: 0,
              color: config.text,
            }}
          />
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: config.text,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {step.name || step.id}
          </span>
          <span
            style={{
              fontSize: 10,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              opacity: 0.6,
              fontWeight: 500,
              flexShrink: 0,
            }}
          >
            {step.kind}
          </span>
        </div>
        {subtitle && (
          <div
            style={{
              fontSize: 11,
              color: "#71717a",
              marginTop: 4,
              fontFamily: "monospace",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {subtitle}
          </div>
        )}
        {step.if && (
          <div
            style={{
              fontSize: 10,
              fontStyle: "italic",
              color: "#a1a1aa",
              marginTop: 4,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            if: {step.if}
          </div>
        )}
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        style={{
          background: "#d4d4d8",
          width: 8,
          height: 8,
          border: "none",
        }}
      />
    </>
  );
}

export const StepNode = memo(StepNodeComponent);
