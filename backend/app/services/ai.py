import json
import re
from flask import current_app, g
from groq import Groq


class AIServiceError(RuntimeError):
    pass


def _provider_error_message(exc):
    status_code = getattr(exc, "status_code", None)
    model = current_app.config.get("GROQ_MODEL", "openai/gpt-oss-20b")
    if status_code == 401:
        return "Groq authentication failed. Verify GROQ_API_KEY in the Render environment."
    if status_code == 403:
        return f"The Groq account is not permitted to use model '{model}'. Verify model access and GROQ_MODEL."
    if status_code == 404:
        return f"Groq could not find model '{model}'. Set GROQ_MODEL to an active model available to your account."
    if status_code == 413:
        return "The request is too large for Groq. Reduce the prompt size and try again."
    if status_code == 429:
        return "Groq rate limit or usage quota reached. Review your account limits or retry after the limit resets."
    if status_code in {400, 422}:
        return f"Groq rejected the request for model '{model}'. Check its token limit and support for the requested response format."
    if isinstance(status_code, int) and status_code >= 500:
        return "Groq is temporarily unavailable. Please retry shortly."

    error_type = type(exc).__name__
    if error_type == "APITimeoutError":
        return "The Groq request timed out. Please retry; if this persists, check Groq availability."
    if error_type == "APIConnectionError":
        return "Could not connect to Groq. Check the Render service's outbound connectivity and retry."

    request_id = getattr(g, "request_id", None)
    if request_id:
        return f"The AI provider request failed. Check Render logs for request ID {request_id}."
    return "The AI provider request failed. Check the Render service logs for details."


def _log_provider_error(exc, message):
    request_id = getattr(g, "request_id", "unavailable")
    model = current_app.config.get("GROQ_MODEL", "openai/gpt-oss-20b")
    status_code = getattr(exc, "status_code", "unavailable")
    current_app.logger.exception(
        "%s (request_id=%s, model=%s, status=%s)",
        message,
        request_id,
        model,
        status_code,
    )


def _client(timeout=30.0):
    key = current_app.config.get("GROQ_API_KEY", "").strip()
    if not key:
        raise AIServiceError(
            "AI is not configured. Set GROQ_API_KEY in backend/.env for local use or in the Render service environment."
        )
    return Groq(api_key=key, timeout=timeout, max_retries=2)


def completion(messages, *, temperature=0.1, max_tokens=1800, json_mode=False, timeout=30.0):
    kwargs = {
        "model": current_app.config.get("GROQ_MODEL", "openai/gpt-oss-20b"),
        "messages": messages,
        "temperature": temperature,
        "max_completion_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        response = _client(timeout=timeout).chat.completions.create(**kwargs)
        if not response.choices:
            raise AIServiceError("The AI provider returned no answer. Please retry.")
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise AIServiceError("The AI provider returned an empty response. Please retry.")
        return content.strip()
    except AIServiceError:
        raise
    except Exception as exc:
        _log_provider_error(exc, "Groq request failed")
        raise AIServiceError(_provider_error_message(exc)) from exc


def completion_stream(messages, *, temperature=0.1, max_tokens=1800, timeout=60.0):
    kwargs = {
        "model": current_app.config.get("GROQ_MODEL", "openai/gpt-oss-20b"),
        "messages": messages,
        "temperature": temperature,
        "max_completion_tokens": max_tokens,
        "stream": True,
    }
    try:
        stream = _client(timeout=timeout).chat.completions.create(**kwargs)
        yielded_content = False
        for chunk in stream:
            if not chunk.choices:
                continue
            content = chunk.choices[0].delta.content
            if isinstance(content, str) and content:
                yielded_content = True
                yield content
        if not yielded_content:
            raise AIServiceError("The AI provider returned an empty response. Please retry.")
    except AIServiceError:
        raise
    except Exception as exc:
        _log_provider_error(exc, "Groq streaming request failed")
        raise AIServiceError(_provider_error_message(exc)) from exc


def json_completion(messages, *, temperature=0.0, max_tokens=2200, timeout=30.0):
    raw = completion(messages, temperature=temperature, max_tokens=max_tokens, json_mode=True, timeout=timeout)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Some models occasionally wrap JSON in a Markdown fence despite JSON mode.
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        raise AIServiceError("The AI provider returned an invalid structured response. Please retry.")
