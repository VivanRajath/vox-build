import { useState } from "react";

const BLANK_IDEAS = [
  "A landing page for a South Indian café called Filter Kaapi",
  "A portfolio for a wedding photographer in Jaipur",
  "A yoga studio site with class timings and pricing",
];
const EDIT_IDEAS = ["Make the header dark green", "Add a testimonials section", "Make this bigger", "Undo that"];

export default function Composer({ busy, isBlank, onCommand }) {
  const [text, setText] = useState("");

  const submit = (e) => {
    e.preventDefault();
    const value = text.trim();
    if (!value) return;
    onCommand(value);
    setText("");
  };

  return (
    <div className="composer">
      <div className="ideas" aria-label="Suggestions">
        {(isBlank ? BLANK_IDEAS : EDIT_IDEAS).map((idea) => (
          <button key={idea} className="idea" onClick={() => setText(idea)} disabled={!!busy}>{idea}</button>
        ))}
      </div>
      <form className="composer-form" onSubmit={submit}>
        <label className="sr-only" htmlFor="command">{isBlank ? "Describe your website" : "Describe a change"}</label>
        <input
          id="command"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={isBlank ? "Or type: describe your website" : "Or type a change"}
          disabled={!!busy}
          autoComplete="off"
        />
        <button type="submit" className="btn primary" disabled={!text.trim() || !!busy}>Send</button>
      </form>
    </div>
  );
}
