export default function History({ versions, current, tierLabel, onUndo, onRestore }) {
  const items = [...versions].reverse();
  return (
    <div className="panel history">
      <div className="history-head">
        <h2>Versions</h2>
        <button className="ghost small" onClick={onUndo} disabled={current === 0}>↶ Undo</button>
      </div>
      <ul>
        {items.map((v) => (
          <li key={v.n} className={v.n === current ? "current" : v.n > current ? "undone" : ""}>
            <button onClick={() => onRestore(v.n)} disabled={v.n === current}>
              <span className="v-num">v{v.n}</span>
              <span className="v-summary">{v.summary}</span>
              {v.tier && <span className="tier">{tierLabel[v.tier] || v.tier}</span>}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
