import { useMemo } from "react";
import { makeStyles, tokens } from "@fluentui/react-components";
import { CopyButton } from "./CopyButton";

interface JsonViewProps {
  data: unknown;
}

interface Token {
  text: string;
  color: string;
}

const useStyles = makeStyles({
  wrapper: {
    position: "relative",
    "&:hover button": {
      opacity: 1,
    },
  },
  pre: {
    fontSize: "12px",
    fontFamily: "'JetBrains Mono', 'Cascadia Code', monospace",
    backgroundColor: tokens.colorNeutralBackground3,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: "6px",
    padding: "12px",
    overflowX: "auto",
    maxHeight: "320px",
    margin: 0,
  },
  copyBtn: {
    position: "absolute",
    top: "8px",
    right: "8px",
    opacity: 0,
    transitionProperty: "opacity",
    transitionDuration: "0.15s",
  },
  null: {
    color: tokens.colorNeutralForeground4,
    fontStyle: "italic",
    fontSize: "13px",
  },
});

function tokenize(json: string): Token[] {
  const result: Token[] = [];
  const regex =
    /("(?:\\u[\dA-Fa-f]{4}|\\[^u]|[^\\"])*"(?:\s*:)?|\b(?:true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g;

  let lastIndex = 0;
  let match;

  while ((match = regex.exec(json)) !== null) {
    if (match.index > lastIndex) {
      result.push({ text: json.slice(lastIndex, match.index), color: "" });
    }

    const value = match[0];
    let color = "#0078d4"; // number - blue
    if (value.startsWith('"')) {
      color = value.endsWith(":") ? "#8a8886" : "#107c10"; // key: gray, string: green
    } else if (/^(?:true|false)$/.test(value)) {
      color = "#ca5010"; // boolean: orange
    } else if (value === "null") {
      color = "#8a8886"; // null: gray
    }

    result.push({ text: value, color });
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < json.length) {
    result.push({ text: json.slice(lastIndex), color: "" });
  }

  return result;
}

export function JsonView({ data }: JsonViewProps) {
  const styles = useStyles();

  if (data === undefined || data === null) {
    return <span className={styles.null}>null</span>;
  }

  const json = JSON.stringify(data, null, 2);
  const jsonTokens = useMemo(() => tokenize(json), [json]);

  return (
    <div className={styles.wrapper}>
      <pre className={styles.pre}>
        {jsonTokens.map((t, i) =>
          t.color ? (
            <span key={i} style={{ color: t.color }}>
              {t.text}
            </span>
          ) : (
            t.text
          ),
        )}
      </pre>
      <div className={styles.copyBtn}>
        <CopyButton text={json} label="Copy JSON" />
      </div>
    </div>
  );
}
