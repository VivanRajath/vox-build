import { useEffect, useRef } from "react";

const TIME = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });

export default function ActivityLog({ entries, tierLabel, isBlank }) {
  const endRef = useRef(null);
  // Braces matter: newer browsers return a Promise from scrollIntoView, which React would treat as a cleanup.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [entries.length]);

  if (entries.length === 0) {
    return (
      <div className="feed-empty">
        <p className="feed-empty-title">{isBlank ? "Start with a description" : "No changes yet in this session"}</p>
        <p>
          {isBlank
            ? "Tell Vox what the business is, who it's for and how it should feel. A researcher picks colours, fonts and photos before the first version is built."
            : "Ask for a change by voice or type it below. Each request and its result appears here."}
        </p>
      </div>
    );
  }

  return (
    <ol className="feed">
      {entries.map((e) => (
        <li key={e.id} className={`entry is-${e.kind}`}>
          <div className="entry-head">
            <span className="entry-who">{e.kind === "user" ? "You" : e.kind === "research" ? "Researcher" : "Vox"}</span>
            {e.tier && e.kind !== "user" && <span className="entry-tier">{tierLabel[e.tier] || e.tier}</span>}
            <time className="entry-time">{TIME.format(e.ts)}</time>
          </div>
          <p className="entry-text">{e.text}</p>
          {e.palette && (
            <div className="swatches" aria-label="Researched palette">
              {Object.entries(e.palette).map(([name, color]) => (
                <span key={name} className="swatch" style={{ background: color }} title={`${name} ${color}`} />
              ))}
            </div>
          )}
          {e.images?.length > 0 && (
            <div className="thumbs">
              {e.images.map((img) => (
                <img key={img.path} src={img.src} alt={img.alt} title={img.alt} loading="lazy" />
              ))}
            </div>
          )}
        </li>
      ))}
      <li ref={endRef} aria-hidden="true" className="feed-end" />
    </ol>
  );
}
