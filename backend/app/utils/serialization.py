from datetime import datetime
import re
from .text import safe_list

PROFILE_FIELDS = [
    "full_name", "headline", "phone", "email", "github_url", "linkedin_url",
    "website_url", "resume_url", "location", "objective", "preferred_roles",
    "years_experience", "availability", "public_fields"
]


def serialize_profile(obj):
    result = {field: getattr(obj, field) for field in PROFILE_FIELDS}
    result["public_fields"] = obj.public_fields or []
    result["updated_at"] = obj.updated_at.isoformat() if obj.updated_at else None
    return result


def serialize_skill(obj):
    return {
        "id": obj.id, "name": obj.name, "category": obj.category, "level": obj.level,
        "years_experience": obj.years_experience, "evidence": obj.evidence or "",
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }


def serialize_education(obj):
    return {
        "id": obj.id, "institution": obj.institution, "degree": obj.degree or "",
        "stream": obj.stream or "", "start_year": obj.start_year,
        "end_year": obj.end_year, "is_current": obj.is_current,
        "grade_type": obj.grade_type or "", "grade_value": obj.grade_value or "",
        "location": obj.location or "", "description": obj.description or "",
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }


def serialize_project(obj):
    return {
        "id": obj.id, "name": obj.name, "description": obj.description or "",
        "tech_stack": safe_list(obj.tech_stack), "custom_fields": safe_list(obj.custom_fields),
        "role": obj.role or "", "live_url": obj.live_url or "",
        "github_url": obj.github_url or "",
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }


def _serialize_experience_date(value):
    text = value or ""
    for source_format, output_format in (("%Y-%m-%d", "%d/%m/%Y"), ("%Y-%m", "%m/%Y")):
        try:
            return datetime.strptime(text, source_format).strftime(output_format)
        except ValueError:
            continue
    legacy = re.fullmatch(r"(19\d{2}|20\d{2}|21\d{2})-(0?[1-9]|1[0-2])", text)
    if legacy:
        return f"{int(legacy.group(2)):02d}/{legacy.group(1)}"
    return text


def serialize_experience(obj):
    return {
        "id": obj.id, "company": obj.company, "title": obj.title,
        "employment_type": obj.employment_type or "", "location": obj.location or "", "work_mode": obj.work_mode or "",
        "start_date": _serialize_experience_date(obj.start_date), "end_date": _serialize_experience_date(obj.end_date), "is_current": obj.is_current,
        "description": obj.description or "", "achievements": safe_list(obj.achievements),
        "tech_stack": safe_list(obj.tech_stack),
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }
