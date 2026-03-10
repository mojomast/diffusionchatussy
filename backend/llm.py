"""
Tone-Field Chat — LLM Client

Handles communication with any OpenAI-compatible API provider.
Builds the rewrite prompt and calls the configured model.

For Mercury 2 (Inception): supports real diffusion streaming via
the `diffusing: true` API parameter, which streams intermediate
denoising steps — the actual diffusion process, not a simulation.

For all other providers: standard non-streaming completion.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

import httpx

from config import state, ModelConfig, ToneConfig

logger = logging.getLogger("tonechat.llm")


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_rewrite_prompt(message: str, tone: ToneConfig) -> str:
    """Construct the system prompt for tone rewriting."""

    strength_note = ""
    if tone.strength < 100:
        strength_note = (
            f"\nTone strength: {tone.strength}%. "
            f"Apply the tone partially — blend the original voice with the target tone. "
            f"At 0% keep the message exactly as-is. At 100% fully rewrite."
        )

    system_prompt = (
        f"You are a tone rewriter. Rewrite user messages to match a specific tone.\n\n"
        f"Tone: {tone.tone_name}\n"
        f"Description: {tone.description}\n"
        f"{strength_note}\n\n"
        f"Rules:\n"
        f"- ALWAYS produce a rewritten version, even for very short messages like 'hi' or 'ok'\n"
        f"- For short messages, expand slightly to express the tone (e.g. 'hi' → 'Hey there, good to see you!')\n"
        f"- Preserve the original meaning exactly\n"
        f"- Do NOT add information the user did not express\n"
        f"- Do NOT remove the user's intent\n"
        f"- Only adjust the tone, word choice, and style\n"
        f"- Return ONLY the rewritten message text, nothing else\n"
        f"- Do NOT add quotes around the message\n"
        f"- The rewritten message MUST be different from the original\n"
        f"- Keep the message roughly the same length (short messages can be slightly longer)"
    )

    return system_prompt


# ---------------------------------------------------------------------------
# Check if the current config supports real diffusion
# ---------------------------------------------------------------------------

def supports_diffusion(model_config: ModelConfig) -> bool:
    """
    Real diffusion streaming is only available via the Inception API
    (direct or through a provider that passes through the diffusing param).
    Mercury 2 on Inception's own endpoint supports it natively.
    """
    # Direct Inception API
    if model_config.provider == "inception":
        return True
    # If the user has manually pointed at Inception's API
    base = model_config.resolved_base_url().lower()
    if "inceptionlabs.ai" in base:
        return True
    return False


# ---------------------------------------------------------------------------
# Build request headers and payload
# ---------------------------------------------------------------------------

def _build_request(
    message: str,
    model_config: ModelConfig,
    system_prompt: str,
    stream: bool = False,
    diffusing: bool = False,
) -> tuple[str, dict, dict]:
    """Build URL, headers, and payload for the LLM API call."""

    base_url = model_config.resolved_base_url()
    if not base_url:
        raise ValueError(f"No base_url configured for provider '{model_config.provider}'")

    url = f"{base_url}/chat/completions"

    headers: dict[str, str] = {
        "Content-Type": "application/json",
    }

    if model_config.api_key:
        headers["Authorization"] = f"Bearer {model_config.api_key}"

    if model_config.provider == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/tonechat"
        headers["X-Title"] = "ToneChat"

    payload: dict = {
        "model": model_config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        "max_tokens": model_config.max_tokens,
        "temperature": model_config.temperature,
    }

    # Only include params that the provider supports
    if model_config.top_p != 1.0:
        payload["top_p"] = model_config.top_p
    if model_config.frequency_penalty != 0.0:
        payload["frequency_penalty"] = model_config.frequency_penalty
    if model_config.presence_penalty != 0.0:
        payload["presence_penalty"] = model_config.presence_penalty

    if stream:
        payload["stream"] = True

    # Mercury 2 diffusion mode — the real deal
    if diffusing:
        payload["diffusing"] = True
        payload["stream"] = True  # diffusing requires streaming

    return url, headers, payload


# ---------------------------------------------------------------------------
# Standard (non-streaming) LLM call
# ---------------------------------------------------------------------------

async def call_llm(
    message: str,
    model_config: ModelConfig,
    system_prompt: str,
) -> str:
    """Standard non-streaming call. Works with any OpenAI-compatible API."""

    url, headers, payload = _build_request(message, model_config, system_prompt)

    logger.info(f"LLM request → {model_config.provider}/{model_config.model}")

    async with httpx.AsyncClient(timeout=model_config.timeout) as client:
        response = await client.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            error_body = response.text
            logger.error(f"LLM API error {response.status_code}: {error_body}")
            raise RuntimeError(
                f"LLM API returned {response.status_code}: {error_body[:500]}"
            )

        data = response.json()

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        logger.error(f"Unexpected LLM response structure: {data}")
        raise RuntimeError(f"Could not parse LLM response: {e}")

    return content.strip().strip('"').strip("'")


# ---------------------------------------------------------------------------
# Diffusion streaming call — yields real denoising steps from Mercury 2
# ---------------------------------------------------------------------------

async def call_llm_diffusion(
    message: str,
    model_config: ModelConfig,
    system_prompt: str,
) -> AsyncGenerator[str, None]:
    """
    Stream diffusion denoising steps from Mercury 2.

    With `diffusing: true`, each SSE chunk's `choice.delta.content`
    contains the FULL current state of the output being refined —
    not incremental tokens. The text resolves from noise to final
    through the model's actual denoising process.

    Yields each intermediate state as a string.
    """

    url, headers, payload = _build_request(
        message, model_config, system_prompt,
        stream=True, diffusing=True,
    )

    logger.info(f"LLM diffusion request → {model_config.provider}/{model_config.model}")

    async with httpx.AsyncClient(timeout=model_config.timeout) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as response:
            if response.status_code != 200:
                # Read the error body
                error_chunks = []
                async for chunk in response.aiter_bytes():
                    error_chunks.append(chunk.decode("utf-8", errors="replace"))
                error_body = "".join(error_chunks)
                logger.error(f"LLM diffusion API error {response.status_code}: {error_body}")
                raise RuntimeError(
                    f"LLM API returned {response.status_code}: {error_body[:500]}"
                )

            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                # Process complete SSE lines
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()

                    if not line:
                        continue
                    if line == "data: [DONE]":
                        return
                    if not line.startswith("data: "):
                        continue

                    json_str = line[6:]  # Strip "data: " prefix
                    if not json_str.startswith("{"):
                        continue

                    try:
                        data = json.loads(json_str)
                        for choice in data.get("choices", []):
                            delta = choice.get("delta", {})
                            content = delta.get("content")
                            if content is not None:
                                # Each content is the full current denoised state
                                yield content
                    except json.JSONDecodeError:
                        logger.debug(f"Skipping unparseable SSE chunk: {json_str[:100]}")
                        continue


# ---------------------------------------------------------------------------
# Main rewrite function — non-streaming (returns final result)
# ---------------------------------------------------------------------------

async def rewrite_message(message: str) -> dict:
    """
    Rewrite a chat message. Returns dict with 'rewritten' and 'rewrite_status'.
    Status values: 'ok', 'passthrough', 'no_key', 'error'.
    """

    tone = state.tone
    model_config = state.model

    result: dict = {"rewritten": message, "rewrite_status": "passthrough"}

    if tone.strength == 0:
        result["rewrite_status"] = "passthrough"
        return result

    if not model_config.api_key and model_config.provider not in ("local", "custom"):
        logger.warning("No API key configured — returning original message")
        result["rewrite_status"] = "no_key"
        return result

    try:
        system_prompt = build_rewrite_prompt(message, tone)
        rewritten = await call_llm(message, model_config, system_prompt)

        if not rewritten:
            logger.warning("LLM returned empty response — using original")
            result["rewrite_status"] = "error"
            return result

        result["rewritten"] = rewritten
        result["rewrite_status"] = "ok"
        return result

    except Exception as e:
        logger.error(f"Rewrite failed: {e}")
        result["rewrite_status"] = "error"
        result["error"] = str(e)[:200]
        return result


# ---------------------------------------------------------------------------
# Diffusion rewrite — async generator yielding intermediate steps
# ---------------------------------------------------------------------------

async def rewrite_message_diffusion(message: str) -> AsyncGenerator[str, None]:
    """
    Rewrite a chat message using Mercury 2's real diffusion process.
    Yields intermediate denoising states as they arrive from the model.
    The final yielded value is the fully resolved rewrite.

    Falls back to a single yield of the original message on error.
    """

    tone = state.tone
    model_config = state.model

    if tone.strength == 0:
        yield message
        return

    if not model_config.api_key and model_config.provider not in ("local", "custom"):
        logger.warning("No API key configured — returning original message")
        yield message
        return

    try:
        system_prompt = build_rewrite_prompt(message, tone)

        step_count = 0
        last_content = message

        async for content in call_llm_diffusion(message, model_config, system_prompt):
            last_content = content
            step_count += 1
            yield content

        logger.info(f"Diffusion complete: {step_count} denoising steps")

        # If we got nothing, yield original
        if step_count == 0:
            yield message

    except Exception as e:
        logger.error(f"Diffusion rewrite failed: {e}")
        yield message
