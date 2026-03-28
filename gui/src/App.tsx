import { Routes, Route, NavLink } from "react-router-dom";
import { Activity, FileCode2, Zap } from "lucide-react";
import { cn } from "./lib/utils";
import { RunsList } from "./components/RunsList";
import { RunDetail } from "./components/RunDetail";
import { WorkflowsList } from "./components/WorkflowsList";
import { WorkflowGraph } from "./components/WorkflowGraph";

function SidebarLink({
  to,
  icon: Icon,
  children,
}: {
  to: string;
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
          isActive
            ? "bg-sidebar-active text-sidebar-text-active"
            : "text-sidebar-text hover:bg-sidebar-hover hover:text-sidebar-text-active"
        )
      }
    >
      <Icon className="w-4 h-4" />
      {children}
    </NavLink>
  );
}

export default function App() {
  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-56 bg-sidebar flex flex-col shrink-0 border-r border-zinc-800">
        <div className="px-4 py-5 flex items-center gap-2.5">
          <Zap className="w-5 h-5 text-blue-400" />
          <span className="text-sm font-semibold text-white tracking-tight">
            CheckpointFlow
          </span>
        </div>
        <nav className="flex-1 px-3 space-y-1">
          <SidebarLink to="/" icon={Activity}>
            Runs
          </SidebarLink>
          <SidebarLink to="/workflows" icon={FileCode2}>
            Workflows
          </SidebarLink>
        </nav>
        <div className="px-4 py-3 text-xs text-zinc-600">
          Dashboard v0.1
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-zinc-50">
        <Routes>
          <Route path="/" element={<RunsList />} />
          <Route path="/runs/:id" element={<RunDetail />} />
          <Route path="/workflows" element={<WorkflowsList />} />
          <Route path="/workflows/:path" element={<WorkflowGraph />} />
        </Routes>
      </main>
    </div>
  );
}
