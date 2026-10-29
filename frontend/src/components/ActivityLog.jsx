import { useEffect, useRef } from "react";

export default function ActivityLog({ entries, tierLabel }) {
  const endRef = useRef(null);
  // Braces matter: newer browsers return a Promise from scrollIntoView, which React would treat as a cleanup.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [entries.length]);

  return (
    <div className="panel log">
      <h2>Activity</h2>
      {entries.length === 0 ? (
        <p className="empty">Your spoken edits will show up here.</p>
      ) : (
        <ul>
          {entries.map((e) => (
            <li key={e.id} className={`log-${e.kind}`}>
              <span className="log-icon" aria-hidden="true" />
              <span className="log-text">
                {e.kind === "user" ? `“${e.text}”` : e.text}
                {e.tier && <span className="tier">{tierLabel[e.tier] || e.tier}</span>}
                {e.palette && (
                  <span className="swatches" aria-label="Researched palette">
                    {Object.entries(e.palette).map(([name, color]) => (
                      <span key={name} className="swatch" style={{ background: color }} title={`${name} ${color}`} />
                    ))}
                  </span>
                )}
                {e.images?.length > 0 && (
                  <span className="thumbs">
                    {e.images.map((img) => (
                      <img key={img.path} src={img.src} alt={img.alt} title={img.alt} loading="lazy" />
                    ))}
                  </span>
                )}
              </span>
            </li>
          ))}
          <li ref={endRef} aria-hidden="true" className="log-end" />
        </ul>
      )}
    </div>
  );
}
