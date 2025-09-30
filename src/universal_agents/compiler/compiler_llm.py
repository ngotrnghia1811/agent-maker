"""Compiler-LLM — lightweight LLM client for interpreting custom user answers.

Only invoked when the user selects "Custom" and types free-form text.
For standard numbered-option selections, no LLM call is needed.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Default configuration for the Compiler-LLM
_DEFAULTS = {
    "provider": "openrouter",
    "model": os.getenv("DEFAULT_OPENROUTER_MODEL", "stepfun/step-3.5-flash:free"),
    "max_tokens": 1024,
    "temperature": 0.0,
}

# Provider → (base_url, api_key_env_var)
_PROVIDER_ENDPOINTS: dict[str, tuple[str, str]] = {
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY"),
    "openai": ("https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY"),
}

_INTERPRET_SYSTEM = (
    "You are a component selector for the universal-agents framework. "
    "Given a user's natural language answer to an interview question, "
    "map it to the corresponding structured field value. "
    "Respond with JSON only — no markdown, no explanation."
)

_REFINE_PROMPT_SYSTEM = (
    "You are a system prompt engineer. Given a user's rough description of what "
    "they want an AI agent to do, produce a polished, specific system prompt. "
    "Output only the refined system prompt text — no JSON, no quotes, no explanation."
)


class CompilerLLM:
    """Lightweight LLM client used during the compilation interview.

    Makes direct httpx calls rather than using the full agent pipeline
    to stay independent of the agents being compiled.
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        self.provider = provider or _DEFAULTS["provider"]
        self.model = model or _DEFAULTS["model"]
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def interpret_custom(
        self,
        question_text: str,
        field_name: str,
        user_text: str,
        valid_values: list[str] | None = None,
    ) -> Any:
        """Interpret a free-form user answer into a structured value.

        Returns a Python value (str, bool, dict, etc.) suitable for
        setting on UserRequirements.
        """
        prompt_parts = [
            f"Interview question: {question_text}",
            f"Target field: {field_name}",
            f"User's free-form answer: {user_text}",
        ]
        if valid_values:
            prompt_parts.append(f"Valid values for this field: {valid_values}")
        prompt_parts.append(
            'Respond with a JSON object: {"value": <the_structured_value>}'
        )

        response = await self._call("\n".join(prompt_parts), system=_INTERPRET_SYSTEM)
        return self._parse_json_value(response)

    async def refine_system_prompt(self, user_draft: str) -> str:
        """Refine a user's rough system prompt description into a polished prompt."""
        response = await self._call(user_draft, system=_REFINE_PROMPT_SYSTEM)
        return response.strip()

    async def explain_compilation(
        self,
        provider: str,
        agent_class: str,
        capabilities: list[str],
    ) -> str:
        """Generate a human-readable summary of why components were chosen."""
        prompt = (
            f"Explain in 2-3 sentences why this agent configuration was selected:\n"
            f"Provider: {provider}\n"
            f"Agent class: {agent_class}\n"
            f"Capabilities: {', '.join(capabilities)}\n"
            f"Be concise and helpful."
        )
        return await self._call(prompt, system="You are a helpful assistant.")

    # ------------------------------------------------------------------
    # Low-level HTTP
    # ------------------------------------------------------------------

    async def _call(self, prompt: str, system: str | None = None) -> str:
        """Make a single chat completion call."""
        url, env_var = _PROVIDER_ENDPOINTS.get(
            self.provider, _PROVIDER_ENDPOINTS["openrouter"]
        )
        api_key = os.environ.get(env_var, "")
        if not api_key:
            logger.warning(
                "No API key for Compiler-LLM (%s=%s). Returning raw input.",
                self.provider, env_var,
            )
            return prompt  # graceful degradation: return uninterpreted text

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "http://localhost"
            headers["X-Title"] = "Universal Agents Compiler"

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": self.model,
            "messages": messages,
            "temperature": _DEFAULTS["temperature"],
            "max_tokens": _DEFAULTS["max_tokens"],
        }

        try:
            resp = await self.client.post(url, headers=headers, json=body)
            if resp.status_code >= 400:
                logger.warning("Compiler-LLM HTTP %d: %s", resp.status_code, resp.text[:200])
                return prompt  # graceful degradation
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return prompt
            return choices[0].get("message", {}).get("content", prompt)
        except (httpx.HTTPError, Exception) as e:
            logger.warning("Compiler-LLM call failed: %s", e)
            return prompt  # graceful degradation

    @staticmethod
    def _parse_json_value(response: str) -> Any:
        """Extract the 'value' field from a JSON response."""
        # Try to find JSON in the response
        text = response.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            text = "\n".join(lines).strip()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "value" in parsed:
                return parsed["value"]
            return parsed
        except json.JSONDecodeError:
            # Return as plain string if not valid JSON
            return text
