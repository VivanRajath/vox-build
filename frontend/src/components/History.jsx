import { UndoIcon } from "./icons.jsx";

const TIME = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

export default function History({ versions, current, tierLabel, onUndo, onRestore }) {
  const items = [...versions].reverse();
  return (
    <div className="versions">
      <div className="versions-head">
        <p>Click a version to go back to it. New changes continue from the one you pick.</p>
        <button className="btn small" onClick={onUndo} disabled={current === 0}><UndoIcon /> Undo</button>
      </div>
      <ol>
        {items.map((v) => (
          <li key={v.n} className={v.n === current ? "is-current" : v.n > current ? "is-undone" : ""}>
            <button onClick={() => onRestore(v.n)} disabled={v.n === current} aria-current={v.n === current ? "true" : undefined}>
              <span className="v-num">v{v.n}</span>
              <span className="v-body">
                <span className="v-summary">{v.summary}</span>
                <span className="v-meta">
                  {v.ts ? TIME.format(v.ts * 1000) : ""}
                  {v.tier ? `, ${tierLabel[v.tier] || v.tier}` : ""}
                  {v.n === current ? ", showing now" : ""}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}
