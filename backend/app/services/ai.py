import json
import re
from flask import current_app
from groq import Groq


class AIServiceError(RuntimeError):
    pass


def _client(timeout=30.0):
    key = current_app.config.get("GROQ_API_KEY", "").strip()
    if not key:
        raise AIServiceError("AI is not configured yet. Add GROQ_API_KEY to backend/.env and restart Flask.")
    return Groq(api_key=key, timeout=timeout, max_retries=1)


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
        # Avoid sending provider internals/API details back to public clients.
        current_app.logger.exception("Groq request failed: %s", exc)
        raise AIServiceError("The AI service could not complete the request. Check the model/key configuration and try again.") from exc


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
        current_app.logger.exception("Groq streaming request failed: %s", exc)
        raise AIServiceError("The AI service could not complete the request. Check the model/key configuration and try again.") from exc


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
