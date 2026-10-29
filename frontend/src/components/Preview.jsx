import { useEffect, useRef, useState } from "react";

const DEVICES = { desktop: "100%", tablet: "820px", mobile: "390px" };

export default function Preview({ projectId, version, reloadKey, busy, tierLabel, picking, selection, onSelect }) {
  const frameRef = useRef(null);
  const scrollY = useRef(0);
  const [device, setDevice] = useState("desktop");
  const [flash, setFlash] = useState(false);
  const src = `/preview/${projectId}/?v=${version}&r=${reloadKey}`;

  const post = (msg) => frameRef.current?.contentWindow?.postMessage({ source: "voicesite-host", ...msg }, "*");

  useEffect(() => {
    const onMessage = (e) => {
      if (e.source !== frameRef.current?.contentWindow) return;
      if (e.data?.source !== "voicesite") return;
      if (e.data.type === "select") onSelect(e.data.selection);
      else if (e.data.type === "scroll") scrollY.current = e.data.y;
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [onSelect]);

  useEffect(() => {
    post({ type: "pick", on: picking });
  }, [picking]);
  useEffect(() => {
    post({ type: "highlight", path: selection?.path || null });
  }, [selection]);

  useEffect(() => {
    if (reloadKey === 0) return;
    setFlash(true);
    const t = setTimeout(() => setFlash(false), 900);
    return () => clearTimeout(t);
  }, [reloadKey]);

  const onLoad = () => {
    post({ type: "scroll-to", y: scrollY.current });
    post({ type: "pick", on: picking });
    post({ type: "highlight", path: selection?.path || null });
  };

  return (
    <section className="preview">
      <div className="preview-toolbar">
        <div className="device-toggle" role="group" aria-label="Preview size">
          {Object.keys(DEVICES).map((d) => (
            <button key={d} className={d === device ? "active" : ""} onClick={() => setDevice(d)}>
              {d}
            </button>
          ))}
        </div>
        <span className="preview-version">v{version}</span>
      </div>

      <div className="preview-stage">
        <div className={`frame-wrap ${flash ? "flash" : ""} ${picking ? "picking" : ""}`} style={{ width: DEVICES[device] }}>
          <iframe ref={frameRef} key={src} src={src} title="Website preview" onLoad={onLoad} />
        </div>

        {busy && (
          <div className="busy-pill">
            <span className="spinner" />
            <span>
              <strong>{tierLabel[busy.tier] || "Vox"}</strong> is working on “{busy.instruction}”
            </span>
          </div>
        )}
        {picking && <div className="pick-hint">Click any element on the page, then say what to change</div>}
      </div>
    </section>
  );
}
