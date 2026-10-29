import { useEffect, useRef, useState } from "react";
import { DesktopIcon, ExternalIcon, PhoneIcon, TabletIcon } from "./icons.jsx";

const DEVICES = {
  desktop: { width: "100%", label: "Desktop", Icon: DesktopIcon },
  tablet: { width: "820px", label: "Tablet", Icon: TabletIcon },
  mobile: { width: "390px", label: "Mobile", Icon: PhoneIcon },
};

export default function Preview({ projectId, version, latest, reloadKey, busy, tierLabel, picking, selection, onSelect }) {
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
    <section className="preview" aria-label="Website preview">
      <div className="preview-bar">
        <div className="segmented" role="group" aria-label="Preview size">
          {Object.entries(DEVICES).map(([id, { label, Icon }]) => (
            <button key={id} className={id === device ? "is-on" : ""} onClick={() => setDevice(id)} aria-pressed={id === device} title={label}>
              <Icon /> <span>{label}</span>
            </button>
          ))}
        </div>
        <div className="address" title="Preview address">
          <span className="address-path">/preview/{projectId}/</span>
          <span className="address-version">
            v{version}
            {latest > version ? ` of ${latest}` : ""}
          </span>
        </div>
        <a className="icon-btn" href={`/preview/${projectId}/`} target="_blank" rel="noreferrer" title="Open in a new tab" aria-label="Open in a new tab">
          <ExternalIcon />
        </a>
      </div>

      <div className="stage">
        <div className={`frame ${flash ? "is-updated" : ""} ${picking ? "is-picking" : ""}`} style={{ width: DEVICES[device].width }}>
          {busy && (
            <div className="frame-status" role="status">
              <span className="progress" aria-hidden="true" />
              <span className="frame-status-text">
                <strong>{tierLabel[busy.tier] || "Vox"}</strong> is working on "{busy.instruction}"
              </span>
            </div>
          )}
          {picking && !busy && (
            <div className="frame-status is-picking" role="status">
              <span className="frame-status-text">Click any element on the page, then say what to change about it.</span>
            </div>
          )}
          <iframe ref={frameRef} key={src} src={src} title="Website preview" onLoad={onLoad} />
        </div>
      </div>
    </section>
  );
}
