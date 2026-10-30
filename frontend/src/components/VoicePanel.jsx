import { MicIcon, PointerIcon, StopIcon, CloseIcon } from "./icons.jsx";

const STATUS = {
  idle: "Talk to Vox",
  connecting: "Connecting…",
  ringing: "Connecting…",
  active: "Listening",
  ended: "Talk to Vox",
};

// Relative bar heights; the live volume scales them.
const BARS = [0.45, 0.8, 1, 0.65, 0.35];

export default function VoicePanel({ voice, config, aiReady, onOpenSettings, picking, onTogglePick, selection, onClearSelection, isBlank }) {
  const live = voice.state === "active";
  const connecting = voice.state === "connecting" || voice.state === "ringing";
  const voiceReady = config?.voice_enabled;
  const level = Math.min(voice.volume || 0, 1);

  return (
    <section className="voice" aria-label="Voice">
      <button
        className={`talk ${live ? "is-live" : ""} ${connecting ? "is-connecting" : ""}`}
        onClick={live || connecting ? voice.stop : voice.start}
        disabled={!voiceReady}
      >
        <span className="talk-icon">{live ? <StopIcon /> : <MicIcon />}</span>
        <span className="talk-label">
          <strong>{voiceReady ? STATUS[voice.state] || "Talk to Vox" : "Voice is off"}</strong>
          <span>
            {!voiceReady
              ? "This server has no Bolna agent. Type below instead."
              : live
                ? "Say what to build or change. Tap to end."
                : connecting
                  ? "Allow the microphone if your browser asks."
                  : isBlank
                    ? "Describe the website you want, out loud."
                    : "Ask for any change, out loud."}
          </span>
        </span>
        <span className="meter" aria-hidden="true">
          {BARS.map((h, i) => (
            <i key={i} style={{ transform: `scaleY(${live ? 0.15 + h * level * 0.85 + 0.05 : 0.15})` }} />
          ))}
        </span>
      </button>

      {live && (
        <button className="text-btn" onClick={voice.toggleMute}>
          {voice.muted ? "Unmute microphone" : "Mute microphone"}
        </button>
      )}

      {voice.error && <p className="notice is-error" role="alert">{voice.error}</p>}
      {!aiReady && (
        <p className="notice is-error">
          No AI model is set up, so changes can't be made yet.{" "}
          <button className="text-btn" onClick={onOpenSettings}>Add an API key in Settings</button>
        </p>
      )}

      <div className="target">
        <button className={`tool-btn ${picking ? "is-on" : ""}`} onClick={onTogglePick} disabled={isBlank} aria-pressed={picking}>
          <PointerIcon /> {picking ? "Click an element on the page" : "Point at an element"}
        </button>
        {selection && (
          <span className="selection" title={selection.path}>
            <span className="selection-label">{selection.label}</span>
            <button className="icon-btn small" onClick={onClearSelection} aria-label="Clear selection"><CloseIcon /></button>
          </span>
        )}
      </div>
    </section>
  );
}
