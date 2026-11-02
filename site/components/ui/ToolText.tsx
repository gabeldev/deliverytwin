// Renders a verbatim tool response: tab-separated blocks become real tables, the rest stays
// as preformatted text. Content is never rewritten, only laid out.
import s from "./tooltext.module.css";

export default function ToolText({ text, maxLines }: { text: string; maxLines?: number }) {
  let lines = text.split("\n");
  const cut = maxLines !== undefined && lines.length > maxLines;
  if (cut) lines = lines.slice(0, maxLines);
  const blocks: { table: boolean; lines: string[] }[] = [];
  for (const ln of lines) {
    const table = ln.includes("\t");
    const last = blocks[blocks.length - 1];
    if (last && last.table === table) last.lines.push(ln);
    else blocks.push({ table, lines: [ln] });
  }
  return (
    <div className={s.wrap}>
      {blocks.map((b, i) => b.table ? (
        <div key={i} className={s.scroll}>
          <table className={s.table}>
            <thead><tr>{b.lines[0].split("\t").map((c, k) => <th key={k} scope="col">{c}</th>)}</tr></thead>
            <tbody>{b.lines.slice(1).map((r, k) => <tr key={k}>{r.split("\t").map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody>
          </table>
        </div>
      ) : (
        <pre key={i} className={s.pre}>{b.lines.join("\n")}</pre>
      ))}
      {cut && <pre className={s.pre}>…</pre>}
    </div>
  );
}
