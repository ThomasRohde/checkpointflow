import { useMemo } from "react";

interface JsonViewProps {
  data: unknown;
  className?: string;
}

interface Token {
  text: string;
  cls: string;
}

function tokenize(json: string): Token[] {
  const tokens: Token[] = [];
  const regex =
    /("(?:\\u[\dA-Fa-f]{4}|\\[^u]|[^\\"])*"(?:\s*:)?|\b(?:true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g;

  let lastIndex = 0;
  let match;

  while ((match = regex.exec(json)) !== null) {
    // Plain text before this token
    if (match.index > lastIndex) {
      tokens.push({ text: json.slice(lastIndex, match.index), cls: "" });
    }

    const value = match[0];
    let cls = "text-blue-600"; // number
    if (value.startsWith('"')) {
      cls = value.endsWith(":") ? "text-zinc-500" : "text-emerald-600";
    } else if (/^(?:true|false)$/.test(value)) {
      cls = "text-amber-600";
    } else if (value === "null") {
      cls = "text-zinc-400";
    }

    tokens.push({ text: value, cls });
    lastIndex = regex.lastIndex;
  }

  // Trailing plain text
  if (lastIndex < json.length) {
    tokens.push({ text: json.slice(lastIndex), cls: "" });
  }

  return tokens;
}

export function JsonView({ data, className }: JsonViewProps) {
  if (data === undefined || data === null) {
    return <span className="text-zinc-400 text-sm italic">null</span>;
  }

  const json = JSON.stringify(data, null, 2);
  const tokens = useMemo(() => tokenize(json), [json]);

  return (
    <pre
      className={`text-xs font-mono bg-zinc-50 border border-zinc-200 rounded-lg p-3 overflow-auto max-h-80 ${className ?? ""}`}
    >
      {tokens.map((t, i) =>
        t.cls ? (
          <span key={i} className={t.cls}>
            {t.text}
          </span>
        ) : (
          t.text
        )
      )}
    </pre>
  );
}
