import json
import re


def safe_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (ValueError, TypeError):
            return [part.strip() for part in value.split(",") if part.strip()]
    return []


def clean_string(value, limit=8000):
    if value is None:
        return ""
    return str(value).strip()[:limit]


def normalize_phrase(value):
    value = (value or "").lower().strip()
    value = value.replace("\u2011", "-").replace("\u2013", "-")
    value = re.sub(r"\.(js|ts)\b", r"\1", value)
    value = re.sub(r"[^a-z0-9+#.\- ]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()
