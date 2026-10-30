from contextvars import ContextVar

import anthropic
import openai

from . import config

OPENAI_COMPATIBLE = {
    "openai": None,
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "groq": "https://api.groq.com/openai/v1",
    "custom": None,  # base URL comes from the user's settings
}

# Lower effort keeps voice edits snappy; full-page rewrites get a bit more.
EFFORT_BY_TIER = {"jnr": "low", "snr": "low", "architect": "medium"}

# Server-side refusal fallback is supported on these models (Claude API only).
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}


class LLMError(RuntimeError):
    pass


class LLMTruncated(LLMError):
    """The model hit max_tokens. Editors escalate instead of giving up."""


# A user's own keys/models (users.ai_settings), set per edit task.
# None means the server's .env configuration only.
_settings: ContextVar[dict | None] = ContextVar("ai_settings", default=None)
_clients: dict[tuple, object] = {}


def use_settings(settings: dict | None) -> None:
    """Applies to the current asyncio task (and tasks it starts)."""
    _settings.set(settings)


def pexels_key() -> str:
    s = _settings.get() or {}
    return s.get("pexels_key") or config.PEXELS_API_KEY


def _target(tier: str) -> tuple[str, list[dict], str, bool]:
    """(provider, credentials to rotate through, model, user_chose_model) for this call.

    Credentials are the user's keys for the provider first, then the server's."""
    s = _settings.get() or {}
    model_tier = config.AGENT_TIER.get(tier, tier)
    pick = (s.get("models") or {}).get(model_tier) or {}
    provider = pick.get("provider") or next(iter(s.get("order") or []), None) or config.LLM_PROVIDER
    chosen = pick.get("model") or ""
    if chosen:
        model = chosen
    elif provider == config.LLM_PROVIDER:
        model = config.model_for(tier)  # honours MODEL_* overrides in .env
    else:
        model = config.DEFAULT_MODELS.get(provider, {}).get(model_tier, "")
    creds = list((s.get("keys") or {}).get(provider, [])) + [{"api_key": k, "base_url": ""} for k in config.ENV_KEYS.get(provider, [])]
    if creds and not model:
        raise LLMError(f"Pick a model for {model_tier} edits in Settings")
    return provider, creds, model, bool(chosen)


def client(provider: str, api_key: str, base_url: str = ""):
    key = (provider, api_key, base_url)
    if key not in _clients:
        if provider == "anthropic":
            _clients[key] = anthropic.AsyncAnthropic(api_key=api_key, timeout=120.0)
        else:
            _clients[key] = openai.AsyncOpenAI(api_key=api_key, base_url=base_url or OPENAI_COMPATIBLE[provider], timeout=120.0)
    return _clients[key]


async def list_models(provider: str, api_key: str, base_url: str = "") -> list[str]:
    """Model ids the key can use. Doubles as a key check."""
    try:
        page = await client(provider, api_key, base_url).models.list()
    except (anthropic.AuthenticationError, openai.AuthenticationError) as e:
        raise LLMError("That API key was rejected") from e
    except (anthropic.APIError, openai.APIError) as e:
        raise LLMError(f"Couldn't list models: {e}") from e
    return sorted(m.id.removeprefix("models/") for m in page.data)


async def complete(system: str, user: str, tier: str, max_tokens: int = 16000, json_mode: bool = False) -> str:
    """json_mode asks OpenAI-compatible providers for a JSON object; callers still parse defensively."""
    provider, creds, model, chosen = _target(tier)
    if not creds:
        raise LLMError("No AI key is set up. Add one in Settings")
    if provider == "anthropic":
        return await _complete_anthropic(creds, system, user, model, tier, max_tokens)
    if provider in OPENAI_COMPATIBLE:
        # Model spillover only when the model wasn't picked by the user.
        fallbacks = [] if chosen else config.RATE_LIMIT_FALLBACKS.get(provider, [])
        return await _complete_openai(creds, provider, fallbacks, system, user, model, tier, max_tokens, json_mode)
    raise LLMError(f"Unknown AI provider {provider!r}")


async def _complete_anthropic(creds: list[dict], system: str, user: str, model: str, tier: str, max_tokens: int) -> str:
    """Tries each key in turn while they're rate limited."""
    for i, cred in enumerate(creds):
        last = i == len(creds) - 1
        api = client("anthropic", cred["api_key"])
        try:
            return await _anthropic_once(api if last else api.with_options(max_retries=0), system, user, model, tier, max_tokens)
        except anthropic.RateLimitError as e:
            if last:
                raise LLMError("The model is rate limited right now, try again in a moment") from e


async def _anthropic_once(api: anthropic.AsyncAnthropic, system: str, user: str, model: str, tier: str, max_tokens: int) -> str:
    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        system=system,
        output_config={"effort": EFFORT_BY_TIER.get(tier, "low")},
        messages=[{"role": "user", "content": user}],
    )
    try:
        if model in FALLBACK_MODELS:
            response = await api.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
            )
        else:
            response = await api.messages.create(**kwargs)
    except anthropic.RateLimitError:
        raise  # the caller moves on to the next key
    except anthropic.APIStatusError as e:
        raise LLMError(f"Model API error ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Could not reach the model API") from e

    if response.stop_reason == "refusal":
        raise LLMError("The model declined this request")
    text = "".join(block.text for block in response.content if block.type == "text")
    if response.stop_reason == "max_tokens":
        raise LLMTruncated("The model ran out of room before finishing")
    return text


def _limit_message(e: openai.APIStatusError) -> str:
    text = str(e.message).lower()
    if "per day" in text or "tpd" in text or "rpd" in text:
        return "The model's daily token limit is used up. Add more quota or switch the model in AI settings"
    return "The model is rate limited right now, try again in a moment"


def _openai_params(provider: str, model: str, tier: str, max_tokens: int, json_mode: bool = False) -> dict:
    # Gemini's compatibility layer and most other OpenAI-compatible servers take max_tokens;
    # newer OpenAI models want max_completion_tokens.
    params = {"max_tokens": max_tokens} if provider in ("gemini", "custom") else {"max_completion_tokens": max_tokens}
    if "gpt-oss" in model:
        # Reasoning models: keep thinking short so voice edits stay quick.
        params["reasoning_effort"] = EFFORT_BY_TIER.get(tier, "low")
    elif provider == "groq" and "qwen" in model:
        # Keep Qwen's <think> output out of the content we parse.
        params["extra_body"] = {"reasoning_format": "hidden"}
    if json_mode:
        params["response_format"] = {"type": "json_object"}
    return params


async def _complete_openai(
    creds: list[dict], provider: str, fallbacks: list[str], system: str, user: str, model: str, tier: str, max_tokens: int,
    json_mode: bool = False,
) -> str:
    # Every key on the chosen model first (same quality), then sibling models.
    models = [model] + [m for m in fallbacks if m != model]
    attempts = [(m, cred) for m in models for cred in creds]
    for i, (candidate, cred) in enumerate(attempts):
        last = i == len(attempts) - 1
        api = client(provider, cred["api_key"], cred.get("base_url", ""))
        # With another attempt left, fail over immediately instead of letting the SDK back off.
        attempt = api if last else api.with_options(max_retries=0)
        try:
            response = await attempt.chat.completions.create(
                model=candidate,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                **_openai_params(provider, candidate, tier, max_tokens, json_mode),
            )
            break
        except openai.RateLimitError as e:
            if last:
                raise LLMError(_limit_message(e)) from e
        except openai.APIStatusError as e:
            # Groq answers 413 when prompt + max_tokens exceeds the model's per-minute quota;
            # a sibling model has its own quota, so treat it like a rate limit.
            if e.status_code == 413 and not last:
                continue
            if e.status_code == 413:
                raise LLMError("This page is too large for the model's per-minute token limit. Try again in a minute or use a bigger model") from e
            raise LLMError(f"Model API error ({e.status_code}): {e.message}") from e
        except openai.APIConnectionError as e:
            raise LLMError("Could not reach the model API") from e

    choice = response.choices[0]
    if choice.finish_reason == "length":
        raise LLMTruncated("The model ran out of room before finishing")
    return choice.message.content or ""
