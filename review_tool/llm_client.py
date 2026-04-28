"""LLM API client wrapper — handles retry, JSON parsing, and schema validation.

Wraps the Anthropic SDK with:
  - Exponential backoff on rate limits (4 retries) and timeouts (2 retries)
  - Immediate fail on auth errors
  - One automatic retry on JSON parse or schema validation failure
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

import anthropic
import jsonschema
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_RATE_LIMIT_DELAYS = (1, 2, 4, 8)   # seconds per attempt; len == max rate-limit retries
_TIMEOUT_MAX_RETRIES = 2

_FENCE_RE = re.compile(r"^```[a-z]*\s*\n?(.*?)\n?\s*```$", re.DOTALL)

_CORRECTIVE_JSON = (
    "Your last output was not valid JSON. "
    "Return only a JSON object matching the required schema. "
    "No prose, no markdown fences."
)
_CORRECTIVE_SCHEMA = (
    "Your last output did not match the required schema. "
    "Validation error: {error}. "
    "Return only a JSON object matching the schema. "
    "No prose, no markdown fences."
)


# ---------------------------------------------------------------------------
# Public exceptions
# ---------------------------------------------------------------------------

class LLMAuthError(Exception):
    """API key is missing or invalid — fail immediately, no retry."""


class LLMValidationError(Exception):
    """LLM output failed schema validation after the one automatic retry."""

    def __init__(self, bad_output: str) -> None:
        preview = bad_output[:300].replace("\n", " ")
        super().__init__(
            f"LLM output failed schema validation after 2 attempts. "
            f"Output preview: {preview!r}"
        )
        self.bad_output = bad_output


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise LLMAuthError(
            "ANTHROPIC_API_KEY is not set. Add it to your .env file or export it as an "
            "environment variable before running."
        )
    return anthropic.Anthropic(api_key=key)


def _strip_fences(text: str) -> str:
    """Remove ```…``` fences if the model wrapped its JSON output in them."""
    text = text.strip()
    m = _FENCE_RE.match(text)
    return m.group(1).strip() if m else text


def _parse_json(text: str) -> Any:
    return json.loads(_strip_fences(text))


def _make_api_call(
    client: anthropic.Anthropic,
    system_prompt: str,
    messages: list[dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """Call the Anthropic API once, with backoff on rate limits and transient errors."""
    rate_retries = 0
    timeout_retries = 0

    while True:
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
                temperature=temperature,
            )
            text_blocks = [b.text for b in resp.content if b.type == "text"]
            if not text_blocks:
                raise ValueError("LLM response contained no text content blocks.")
            return text_blocks[0]

        except anthropic.AuthenticationError as exc:
            raise LLMAuthError(
                "ANTHROPIC_API_KEY is invalid or expired. Check your .env file."
            ) from exc

        except anthropic.RateLimitError as exc:
            if rate_retries >= len(_RATE_LIMIT_DELAYS):
                raise RuntimeError(
                    f"Still rate-limited after {len(_RATE_LIMIT_DELAYS)} retries."
                ) from exc
            delay = _RATE_LIMIT_DELAYS[rate_retries]
            logger.warning(
                "Rate limited (retry %d/%d) — waiting %ds.",
                rate_retries + 1,
                len(_RATE_LIMIT_DELAYS),
                delay,
            )
            time.sleep(delay)
            rate_retries += 1

        except (anthropic.APITimeoutError, anthropic.APIConnectionError) as exc:
            if timeout_retries >= _TIMEOUT_MAX_RETRIES:
                raise RuntimeError(
                    f"API timeout / connection error after {_TIMEOUT_MAX_RETRIES} retries."
                ) from exc
            delay = _RATE_LIMIT_DELAYS[timeout_retries]
            logger.warning(
                "API timeout / connection error (retry %d/%d) — waiting %ds.",
                timeout_retries + 1,
                _TIMEOUT_MAX_RETRIES,
                delay,
            )
            time.sleep(delay)
            timeout_retries += 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def call_with_validation(
    system_prompt: str,
    user_message: str,
    schema: dict,
    model: str = "claude-haiku-4-5-20251001",
    temperature: float = 0,
    max_tokens: int = 1024,
) -> dict:
    """Call the model and return a validated JSON dict.

    Attempts the call up to twice:
      - First attempt: call → parse → validate → return on success
      - On JSON or schema failure: append a corrective turn and retry once
      - Second failure: raise LLMValidationError with the raw output

    Raises:
        LLMAuthError: API key missing or invalid (not retried).
        LLMValidationError: Both attempts produced invalid output.
        RuntimeError: Rate limit or timeout exceeded after all retries.
    """
    client = _get_client()
    messages: list[dict[str, str]] = [{"role": "user", "content": user_message}]

    for attempt in range(2):
        raw = _make_api_call(client, system_prompt, messages, model, temperature, max_tokens)

        try:
            data = _parse_json(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Attempt %d: JSON parse failed — %s", attempt + 1, exc)
            if attempt == 0:
                messages = messages + [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": _CORRECTIVE_JSON},
                ]
                continue
            else:
                raise LLMValidationError(raw) from exc

        try:
            jsonschema.validate(data, schema)
            return data  # type: ignore[return-value]
        except jsonschema.ValidationError as exc:
            logger.warning(
                "Attempt %d: schema validation failed — %s", attempt + 1, exc.message
            )
            if attempt == 0:
                messages = messages + [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": _CORRECTIVE_SCHEMA.format(error=exc.message)},
                ]
                continue
            else:
                raise LLMValidationError(raw) from exc

    raise LLMValidationError("Unexpected: exited retry loop without returning or raising.")
