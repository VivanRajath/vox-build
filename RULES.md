# Hard Rules

## Always
- Record every change as a new version so it can be undone.
- Validate that an edit produces a complete HTML document before committing it.
- Escalate to the next tier when a patch cannot be applied, rather than guessing.
- Keep section ids and data-section attributes stable across edits.
- Reply to the voice agent with one short, speakable sentence.

## Never
- Expose BOLNA_API_KEY or LLM keys to the browser.
- Accept tool calls without the TOOL_SECRET when one is configured.
- Write outside a project's site directory.
- Run generated site code on the server. Sites are only served as static files.

## Boundaries

### code-editor (edit orchestrator)
- Delegates to sub-agents by tier. Does not edit directly.
- **jnr-developer**: small, local patches to index.html.
- **snr-developer**: feature-sized patches to index.html.
- **architect**: full-page rewrites; the final fallback.
