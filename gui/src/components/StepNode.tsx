import { memo } from "react";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { Terminal, Pause, Flag, Circle } from "lucide-react";
import type { WorkflowStep } from "../lib/types";
import { cn, truncate } from "../lib/utils";

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
    shape: string;
  }
> = {
  cli: {
    icon: Terminal,
    bg: "bg-blue-50",
    border: "border-blue-300",
    text: "text-blue-800",
    shape: "rounded-lg",
  },
  await_event: {
    icon: Pause,
    bg: "bg-amber-50",
    border: "border-amber-300",
    text: "text-amber-800",
    shape: "rounded-xl",
  },
  end: {
    icon: Flag,
    bg: "bg-emerald-50",
    border: "border-emerald-300",
    text: "text-emerald-800",
    shape: "rounded-full",
  },
};

const defaultConfig = {
  icon: Circle,
  bg: "bg-zinc-50",
  border: "border-zinc-300",
  text: "text-zinc-700",
  shape: "rounded-lg",
};

function StepNodeComponent({ data }: NodeProps<StepNodeType>) {
  const { step } = data;
  const config = kindConfig[step.kind] ?? defaultConfig;
  const Icon = config.icon;

  const isEnd = step.kind === "end";
  const subtitle =
    step.kind === "cli" && step.command
      ? truncate(step.command, 40)
      : step.kind === "await_event" && step.event_name
        ? step.event_name
        : step.description
          ? truncate(step.description, 40)
          : null;

  return (
    <>
      <Handle type="target" position={Position.Top} className="!bg-zinc-300 !w-2 !h-2 !border-0" />
      <div
        className={cn(
          "border-2 px-4 py-3 shadow-sm transition-shadow",
          config.bg,
          config.border,
          config.shape,
          isEnd ? "min-w-[80px] text-center" : "min-w-[180px] max-w-[260px]",
          data.selected && "ring-2 ring-blue-500 ring-offset-2"
        )}
      >
        <div className="flex items-center gap-2">
          <Icon className={cn("w-4 h-4 shrink-0", config.text)} />
          <span
            className={cn("text-sm font-semibold truncate", config.text)}
          >
            {step.name || step.id}
          </span>
        </div>
        {subtitle && (
          <div className="text-xs text-zinc-500 mt-1 font-mono truncate">
            {subtitle}
          </div>
        )}
        {step.if && (
          <div className="text-[10px] italic text-zinc-400 mt-1 truncate">
            if: {step.if}
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-zinc-300 !w-2 !h-2 !border-0" />
    </>
  );
}

export const StepNode = memo(StepNodeComponent);
