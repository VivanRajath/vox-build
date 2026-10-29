"""Creates (or updates) the Bolna voice agent that drives VoiceSite.

  python scripts/create_agent.py            create a new agent, prints its id
  python scripts/create_agent.py --update   update the agent in BOLNA_AGENT_ID
  python scripts/create_agent.py --dump     print the custom functions as JSON
                                            (to paste into the dashboard Tools tab)

Needs BOLNA_API_KEY and PUBLIC_BASE_URL (the deployed backend's https URL,
e.g. https://voicesite.onrender.com) in .env. TOOL_SECRET is optional.
"""
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

API = os.getenv("BOLNA_API_BASE", "https://api.bolna.ai")
API_KEY = os.getenv("BOLNA_API_KEY", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
TOOL_SECRET = os.getenv("TOOL_SECRET", "")

PROJECT_ID_PARAM = {"type": "string", "description": "The website project id from the system prompt"}

FUNCTIONS = [
    {
        "name": "generate_site",
        "description": "Build a brand new website from a description. Use when the user describes a website they want created from scratch.",
        "pre_call_message": "Love it. Building that for you now.",
        "properties": {
            "project_id": PROJECT_ID_PARAM,
            "description": {"type": "string", "description": "Rich description of the website: business, purpose, style, colours, sections"},
        },
    },
    {
        "name": "edit_site",
        "description": "Change the existing website: colours, text, layout, sections, images, fonts, anything visual. Use for every edit request.",
        "pre_call_message": "On it.",
        "properties": {
            "project_id": PROJECT_ID_PARAM,
            "instruction": {"type": "string", "description": "One clear, self-contained English instruction describing the change"},
        },
    },
    {
        "name": "undo_change",
        "description": "Undo the most recent change to the website. Use when the user says undo, go back, or revert.",
        "pre_call_message": "Undoing that.",
        "properties": {"project_id": PROJECT_ID_PARAM},
    },
    {
        "name": "describe_site",
        "description": "Get an outline of what is currently on the website. Use when the user asks what is on the page.",
        "pre_call_message": "Let me look.",
        "properties": {"project_id": PROJECT_ID_PARAM},
    },
]


def function_schema(fn: dict) -> dict:
    """Dashboard / docs format of a custom function."""
    names = list(fn["properties"])
    value = {
        "method": "POST",
        "param": {name: f"%({name})s" for name in names},
        "url": f"{PUBLIC_BASE_URL}/tools/{fn['name']}",
        "api_token": f"Bearer {TOOL_SECRET}" if TOOL_SECRET else None,
        "headers": {"Content-Type": "application/json"},
    }
    return {
        "name": fn["name"],
        "description": fn["description"],
        "pre_call_message": fn["pre_call_message"],
        "parameters": {"type": "object", "properties": fn["properties"], "required": names},
        "key": "custom_task",
        "value": value,
    }


def api_tools() -> dict:
    """Agent-API format: tool definitions plus per-tool params keyed by name."""
    tools, params = [], {}
    for fn in FUNCTIONS:
        schema = function_schema(fn)
        value = schema.pop("value")
        tools.append(schema)
        params[fn["name"]] = {
            "method": value["method"],
            "url": value["url"],
            "api_token": value["api_token"],
            "param": json.dumps(value["param"]),
        }
    return {"tools": tools, "tools_params": params}


def agent_body() -> dict:
    prompt = (ROOT / "bolna" / "agent_prompt.md").read_text(encoding="utf-8")
    return {
        "agent_config": {
            "agent_name": "VoiceSite - Vox",
            "agent_welcome_message": "Hi, I'm Vox! Tell me what website you'd like to build, or what to change.",
            "tasks": [{
                "task_type": "conversation",
                "toolchain": {"execution": "sequential", "pipelines": [["transcriber", "llm", "synthesizer"]]},
                "tools_config": {
                    "llm_agent": {
                        "agent_type": "simple_llm_agent",
                        "agent_flow_type": "streaming",
                        "llm_config": {
                            "provider": os.getenv("BOLNA_LLM_PROVIDER", "openai"),
                            "model": os.getenv("BOLNA_LLM_MODEL", "gpt-5.4-mini"),
                            "max_tokens": 200,
                            # Reasoning models (gpt-5.x) only accept temperature 1.
                            "temperature": float(os.getenv("BOLNA_LLM_TEMPERATURE", "1")),
                        },
                    },
                    "synthesizer": {
                        "provider": "cartesia",
                        "provider_config": {
                            "voice": os.getenv("BOLNA_VOICE", "Brooke - Big Sister"),
                            "voice_id": os.getenv("BOLNA_VOICE_ID", "e07c00bc-4134-4eae-9ea4-1a55fb45746b"),
                            "model": "sonic-3.5",
                            "language": "en",
                        },
                        "stream": True,
                        "buffer_size": 200,
                        "audio_format": "wav",
                    },
                    "transcriber": {
                        "provider": "deepgram",
                        "model": "nova-3",
                        "language": os.getenv("BOLNA_STT_LANGUAGE", "en"),
                        "stream": True,
                        "encoding": "linear16",
                        "sampling_rate": 16000,
                        "endpointing": 300,
                    },
                    "input": {"provider": "plivo", "format": "wav"},
                    "output": {"provider": "plivo", "format": "wav"},
                    "api_tools": api_tools(),
                },
                "task_config": {
                    # Long sessions with quiet stretches while the user looks at the preview.
                    "call_terminate": 1200,
                    "hangup_after_silence": 120,
                },
            }],
        },
        "agent_prompts": {"task_1": {"system_prompt": prompt}},
    }


def main() -> None:
    if "--dump" in sys.argv:
        print(json.dumps([function_schema(fn) for fn in FUNCTIONS], indent=2))
        return
    if not API_KEY:
        sys.exit("Set BOLNA_API_KEY in .env")
    if not PUBLIC_BASE_URL.startswith("https://"):
        sys.exit("Set PUBLIC_BASE_URL in .env to the deployed backend's https URL (e.g. https://voicesite.onrender.com)")

    headers = {"Authorization": f"Bearer {API_KEY}"}
    if "--update" in sys.argv:
        agent_id = os.getenv("BOLNA_AGENT_ID") or sys.exit("Set BOLNA_AGENT_ID in .env to update")
        r = httpx.put(f"{API}/v2/agent/{agent_id}", headers=headers, json=agent_body(), timeout=30)
    else:
        r = httpx.post(f"{API}/v2/agent", headers=headers, json=agent_body(), timeout=30)

    if r.status_code >= 400:
        sys.exit(f"Bolna returned {r.status_code}: {r.text}")
    data = r.json()
    print(json.dumps(data, indent=2))
    if "agent_id" in data:
        print(f"\nAdd this to .env:\nBOLNA_AGENT_ID={data['agent_id']}")


if __name__ == "__main__":
    main()
