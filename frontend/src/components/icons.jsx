// Small stroke icons, sized by the surrounding font (1em).
const base = { width: "1em", height: "1em", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true };

export const MicIcon = () => (
  <svg {...base}><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
);
export const StopIcon = () => (
  <svg {...base}><rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" stroke="none" /></svg>
);
export const DesktopIcon = () => (
  <svg {...base}><rect x="3" y="4" width="18" height="12" rx="1.5" /><path d="M8 20h8M12 16v4" /></svg>
);
export const TabletIcon = () => (
  <svg {...base}><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M11 18h2" /></svg>
);
export const PhoneIcon = () => (
  <svg {...base}><rect x="7" y="3" width="10" height="18" rx="2" /><path d="M11 18h2" /></svg>
);
export const ExternalIcon = () => (
  <svg {...base}><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></svg>
);
export const LinkIcon = () => (
  <svg {...base}><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" /></svg>
);
export const DownloadIcon = () => (
  <svg {...base}><path d="M12 4v11M7 10l5 5 5-5M5 20h14" /></svg>
);
export const GitHubIcon = () => (
  <svg width="1em" height="1em" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34-.45-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.9 1.52 2.34 1.08 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.65 0 0 .84-.27 2.75 1.02a9.6 9.6 0 0 1 5 0c1.91-1.3 2.75-1.02 2.75-1.02.55 1.38.2 2.4.1 2.65.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.68-4.57 4.93.36.31.68.92.68 1.85v2.74c0 .27.18.58.69.48A10 10 0 0 0 12 2Z" />
  </svg>
);
export const GoogleIcon = () => (
  <svg width="1em" height="1em" viewBox="0 0 24 24" aria-hidden="true">
    <path fill="#4285F4" d="M22.5 12.2c0-.7-.1-1.4-.2-2H12v3.9h5.9a5 5 0 0 1-2.2 3.3v2.7h3.5c2.1-1.9 3.3-4.7 3.3-7.9Z" />
    <path fill="#34A853" d="M12 23c3 0 5.5-1 7.2-2.7l-3.5-2.7c-1 .7-2.2 1.1-3.7 1.1-2.9 0-5.3-1.9-6.1-4.5H2.3v2.8A11 11 0 0 0 12 23Z" />
    <path fill="#FBBC05" d="M5.9 14.2a6.6 6.6 0 0 1 0-4.3V7.1H2.3a11 11 0 0 0 0 9.9l3.6-2.8Z" />
    <path fill="#EA4335" d="M12 5.4c1.6 0 3 .6 4.2 1.6l3.1-3.1A11 11 0 0 0 2.3 7.1l3.6 2.8C6.7 7.3 9.1 5.4 12 5.4Z" />
  </svg>
);
export const PointerIcon = () => (
  <svg {...base}><path d="M5 3l14 7-6 2-2 6L5 3Z" /></svg>
);
export const UndoIcon = () => (
  <svg {...base}><path d="M9 14 4 9l5-5" /><path d="M4 9h10a6 6 0 0 1 0 12h-3" /></svg>
);
export const CloseIcon = () => (
  <svg {...base}><path d="M6 6l12 12M18 6 6 18" /></svg>
);
export const SettingsIcon = () => (
  <svg {...base}><path d="M4 7h10M18 7h2M4 17h4M12 17h8" /><circle cx="16" cy="7" r="2" /><circle cx="10" cy="17" r="2" /></svg>
);

// The VoiceSite mark: three bars of a voice level meter.
export const Logo = () => (
  <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
    <rect width="22" height="22" rx="5" fill="currentColor" />
    <rect x="5" y="8" width="2.6" height="6" rx="1.3" fill="var(--surface)" />
    <rect x="9.7" y="5" width="2.6" height="12" rx="1.3" fill="var(--surface)" />
    <rect x="14.4" y="9.5" width="2.6" height="3" rx="1.3" fill="var(--on-air)" />
  </svg>
);
