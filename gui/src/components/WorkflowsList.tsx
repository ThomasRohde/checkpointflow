import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Input,
  Button,
  Spinner,
  makeStyles,
  tokens,
} from "@fluentui/react-components";
import {
  ArrowSortUpRegular,
  ArrowSortDownRegular,
  SearchRegular,
  FolderRegular,
  DocumentRegular,
} from "@fluentui/react-icons";
import { api } from "../lib/api";
import type { WorkflowFile } from "../lib/types";
import { usePanelNavigation } from "../hooks/usePanelNavigation";

type SortKey = "name" | "relative" | "source";
type SortDir = "asc" | "desc";

function groupBySource(
  workflows: WorkflowFile[],
): Record<string, WorkflowFile[]> {
  const groups: Record<string, WorkflowFile[]> = {};
  for (const wf of workflows) {
    const key = wf.source || "other";
    if (!groups[key]) groups[key] = [];
    groups[key].push(wf);
  }
  return groups;
}

const sourceLabels: Record<string, string> = {
  cwd: "Current Directory",
  home: "Home Directory",
};

const useStyles = makeStyles({
  root: {
    padding: "24px",
    maxWidth: "900px",
    marginLeft: "auto",
    marginRight: "auto",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: "24px",
  },
  titleGroup: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  title: {
    fontSize: "18px",
    fontWeight: 600,
    color: tokens.colorNeutralForeground1,
    margin: 0,
  },
  controls: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  sortButtons: {
    display: "flex",
    alignItems: "center",
    gap: "4px",
  },
  center: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "80px 0",
  },
  empty: {
    textAlign: "center",
    padding: "80px 0",
    color: tokens.colorNeutralForeground4,
  },
  error: {
    padding: "16px",
    borderRadius: "8px",
    border: `1px solid ${tokens.colorPaletteRedBorder2}`,
    backgroundColor: tokens.colorPaletteRedBackground1,
    color: tokens.colorPaletteRedForeground1,
    fontSize: "13px",
  },
  groupHeader: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    marginBottom: "12px",
  },
  groupTitle: {
    fontSize: "13px",
    fontWeight: 500,
    color: tokens.colorNeutralForeground3,
    margin: 0,
  },
  group: {
    marginBottom: "24px",
  },
  wfList: {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  wfButton: {
    width: "100%",
    display: "flex",
    alignItems: "center",
    gap: "12px",
    padding: "12px 16px",
    backgroundColor: tokens.colorNeutralBackground1,
    borderRadius: "8px",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    cursor: "pointer",
    textAlign: "left",
    transitionProperty: "border-color",
    transitionDuration: "0.15s",
  },
  wfContent: {
    flex: 1,
    minWidth: 0,
  },
  wfNameRow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  wfName: {
    fontSize: "13px",
    fontWeight: 500,
    color: tokens.colorNeutralForeground1,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  wfVersion: {
    fontSize: "10px",
    color: tokens.colorNeutralForeground4,
    fontFamily: "monospace",
    flexShrink: 0,
  },
  wfDescription: {
    fontSize: "12px",
    color: tokens.colorNeutralForeground3,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    marginTop: "2px",
  },
  wfPath: {
    fontSize: "12px",
    color: tokens.colorNeutralForeground4,
    fontFamily: "monospace",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
});

export function WorkflowsList() {
  const { openWorkflowGraph } = usePanelNavigation();
  const styles = useStyles();

  const {
    data: workflows,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["workflows"],
    queryFn: api.getWorkflows,
    staleTime: 30_000,
  });

  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const filtered = useMemo(() => {
    if (!workflows) return [];
    const q = search.toLowerCase().trim();
    let result = workflows;
    if (q) {
      result = workflows.filter(
        (wf) =>
          wf.name.toLowerCase().includes(q) ||
          wf.relative.toLowerCase().includes(q) ||
          wf.path.toLowerCase().includes(q),
      );
    }
    return [...result].sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      const cmp = va.localeCompare(vb);
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [workflows, search, sortKey, sortDir]);

  const groups = useMemo(() => groupBySource(filtered), [filtered]);

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <div className={styles.titleGroup}>
          <DocumentRegular style={{ width: 20, height: 20 }} />
          <h1 className={styles.title}>Workflows</h1>
        </div>
        {workflows && workflows.length > 0 && (
          <div className={styles.controls}>
            <Input
              contentBefore={<SearchRegular />}
              placeholder="Search workflows..."
              value={search}
              onChange={(_, data) => setSearch(data.value)}
              size="small"
              style={{ width: 220 }}
            />
            <div className={styles.sortButtons}>
              {(["name", "path"] as const).map((key) => {
                const k: SortKey = key === "path" ? "relative" : key;
                const active = sortKey === k;
                return (
                  <Button
                    key={key}
                    appearance={active ? "primary" : "subtle"}
                    size="small"
                    onClick={() => handleSort(k)}
                    icon={
                      active ? (
                        sortDir === "asc" ? (
                          <ArrowSortUpRegular />
                        ) : (
                          <ArrowSortDownRegular />
                        )
                      ) : undefined
                    }
                    iconPosition="after"
                  >
                    {key === "path" ? "Path" : "Name"}
                  </Button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {isLoading && (
        <div className={styles.center}>
          <Spinner size="medium" />
        </div>
      )}

      {error && (
        <div className={styles.error}>
          Failed to load workflows: {(error as Error).message}
        </div>
      )}

      {workflows && workflows.length === 0 && (
        <div className={styles.empty}>
          <DocumentRegular
            style={{ width: 40, height: 40, opacity: 0.4, margin: "0 auto 12px", display: "block" }}
          />
          <p>No workflows found</p>
        </div>
      )}

      {workflows && workflows.length > 0 && filtered.length === 0 && (
        <div className={styles.empty}>
          <SearchRegular
            style={{ width: 40, height: 40, opacity: 0.4, margin: "0 auto 12px", display: "block" }}
          />
          <p>No workflows match &quot;{search}&quot;</p>
        </div>
      )}

      {filtered.length > 0 && (
        <div>
          {Object.entries(groups).map(([source, files]) => (
            <div key={source} className={styles.group}>
              <div className={styles.groupHeader}>
                <FolderRegular
                  style={{ width: 16, height: 16, color: tokens.colorNeutralForeground4 }}
                />
                <h2 className={styles.groupTitle}>
                  {sourceLabels[source] ?? source}
                </h2>
              </div>
              <div className={styles.wfList}>
                {files.map((wf) => (
                  <button
                    key={wf.path}
                    className={styles.wfButton}
                    onClick={() => openWorkflowGraph(wf.path, wf.name)}
                  >
                    <DocumentRegular
                      style={{ width: 16, height: 16, flexShrink: 0 }}
                    />
                    <div className={styles.wfContent}>
                      <div className={styles.wfNameRow}>
                        <span className={styles.wfName}>{wf.name}</span>
                        {wf.version && (
                          <span className={styles.wfVersion}>
                            v{wf.version}
                          </span>
                        )}
                      </div>
                      {wf.description && (
                        <div className={styles.wfDescription}>
                          {wf.description}
                        </div>
                      )}
                      <div className={styles.wfPath}>{wf.relative}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
