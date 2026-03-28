interface JsonViewProps {
  data: unknown;
  className?: string;
}

function syntaxHighlight(json: string): string {
  return json.replace(
    /("(\\u[\dA-Fa-f]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
    (match) => {
      let cls = "text-blue-600"; // number
      if (match.startsWith('"')) {
        if (match.endsWith(":")) {
          cls = "text-zinc-500"; // key
        } else {
          cls = "text-emerald-600"; // string
        }
      } else if (/true|false/.test(match)) {
        cls = "text-amber-600"; // boolean
      } else if (match === "null") {
        cls = "text-zinc-400"; // null
      }
      return `<span class="${cls}">${match}</span>`;
    }
  );
}

export function JsonView({ data, className }: JsonViewProps) {
  if (data === undefined || data === null) {
    return <span className="text-zinc-400 text-sm italic">null</span>;
  }

  const json = JSON.stringify(data, null, 2);
  const highlighted = syntaxHighlight(json);

  return (
    <pre
      className={`text-xs font-mono bg-zinc-50 border border-zinc-200 rounded-lg p-3 overflow-auto max-h-80 ${className ?? ""}`}
      dangerouslySetInnerHTML={{ __html: highlighted }}
    />
  );
}
