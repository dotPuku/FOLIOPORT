import json
import re
from urllib.parse import urlsplit

from flask import current_app

from .ai import json_completion
from .prompts import RESUME_EXTRACTION_SYSTEM

PROFILE_FIELDS = (
    "full_name", "headline", "email", "phone", "location", "objective",
    "preferred_roles", "github_url", "linkedin_url", "website_url", "resume_url",
)
PROFILE_LIMITS = {
    "full_name": 160, "headline": 220, "email": 255, "phone": 40,
    "location": 180, "objective": 5000, "preferred_roles": 1000,
    "github_url": 500, "linkedin_url": 500, "website_url": 500, "resume_url": 500,
}
SECTION_MAX_TOKENS = {
    "profile": 2200,
    "skills": 3500,
    "education": 4500,
    "projects": 5000,
    "experience": 5000,
}


def _text(value, limit=2000):
    if value is None or isinstance(value, (dict, list, bool)):
        return ""
    return str(value).strip()[:limit]


def _number(value):
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if 0 <= result <= 80 else None


def _year(value):
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        result = int(value)
    except (ValueError, TypeError):
        return None
    return result if 1900 <= result <= 2200 else None


def _boolean(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "current"}


def _string_list(value, item_limit=500, max_items=100):
    if not isinstance(value, list):
        return []
    return [text for item in value[:max_items] if (text := _text(item, item_limit))]


def _url(value, limit=500):
    text = _text(value, limit)
    if not text:
        return ""
    try:
        parsed = urlsplit(text)
    except ValueError:
        return ""
    return text if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _rows(value, limit=60):
    return value[:limit] if isinstance(value, list) else []


def infer_skill_category(name):
    normalized = re.sub(r"[^a-z0-9+#.]+", " ", name.lower()).strip()
    compact = f" {normalized} "
    categories = (
        ("Core Concepts", (
            "data structures", "algorithms", "object oriented programming", "oop",
            "operating systems", "computer networks", "system design", "design patterns",
            "distributed systems", "software architecture", "dbms",
        )),
        ("AI / ML", (
            "ai", "ai ml", "ml", "artificial intelligence", "machine learning", "deep learning", "natural language processing",
            "computer vision", "tensorflow", "pytorch", "scikit learn", "keras", "llm", "generative ai",
        )),
        ("Testing", (
            "testing", "test automation", "test driven development", "jest", "pytest",
            "selenium", "cypress", "playwright",
        )),
        ("DevOps", (
            "devops", "docker", "kubernetes", "aws", "azure", "google cloud", "gcp",
            "cloud computing", "ci cd", "jenkins", "terraform", "ansible", "linux",
        )),
        ("Database", (
            "sql", "mysql", "postgresql", "postgres", "mongodb", "redis", "sqlite",
            "mariadb", "dynamodb", "oracle database",
        )),
        ("Frontend", (
            "frontend", "front end", "html", "css", "react", "vue", "angular", "svelte",
            "tailwind", "bootstrap",
        )),
        ("Backend", (
            "backend", "back end", "node.js", "express", "django", "flask", "fastapi",
            "spring boot", "asp.net", "rest api", "graphql",
        )),
        ("Programming", (
            "python", "javascript", "typescript", "java", "c++", "c#", "golang", "go",
            "rust", "ruby", "php", "kotlin", "swift", "scala",
        )),
        ("Tools", (
            "git", "github", "gitlab", "jira", "postman", "figma", "visual studio code",
        )),
        ("Soft skills", (
            "communication", "leadership", "teamwork", "problem solving", "time management",
            "collaboration", "adaptability",
        )),
    )
    for category, terms in categories:
        if any(f" {term} " in compact for term in terms):
            return category
    return "Other"


def normalize_resume_data(data, section=None):
    allowed_sections = {"profile", "skills", "education", "projects", "experience"}
    if section is not None and section not in allowed_sections:
        raise ValueError("Choose a valid resume section.")
    if section == "profile" and (not isinstance(data, dict) or not isinstance(data.get("profile"), dict)):
        raise ValueError("The AI parser returned an incomplete resume structure. Please try again.")
    if section in allowed_sections - {"profile"} and (
        not isinstance(data, dict) or not isinstance(data.get(section), list)
    ):
        raise ValueError("The AI parser returned an incomplete resume structure. Please try again.")
    if section is not None and isinstance(data, dict):
        data = {
            "profile": data.get("profile", {}),
            "skills": data.get("skills", []),
            "education": data.get("education", []),
            "projects": data.get("projects", []),
            "experience": data.get("experience", []),
        }
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("profile"), dict)
        or any(not isinstance(data.get(key), list) for key in ("skills", "education", "projects", "experience"))
    ):
        raise ValueError("The AI parser returned an incomplete resume structure. Please try again.")

    raw_profile = data.get("profile") if isinstance(data.get("profile"), dict) else {}
    profile = {field: _text(raw_profile.get(field), PROFILE_LIMITS[field]) for field in PROFILE_FIELDS}
    profile["years_experience"] = _number(raw_profile.get("years_experience"))
    for field in ("github_url", "linkedin_url", "website_url", "resume_url"):
        profile[field] = _url(profile[field])

    skills = []
    for row in _rows(data.get("skills"), 100):
        if not isinstance(row, dict):
            continue
        name = _text(row.get("name"), 160)
        category = _text(row.get("category"), 100)
        if name and (not category or category.casefold() == "other"):
            category = infer_skill_category(name)
        skills.append({
            "name": name,
            "category": category or ("Other" if name else ""),
            "level": _text(row.get("level"), 50),
            "years_experience": _number(row.get("years_experience")),
            "evidence": _text(row.get("evidence"), 4000),
        })

    education = []
    for row in _rows(data.get("education")):
        if not isinstance(row, dict):
            continue
        education.append({
            "institution": _text(row.get("institution"), 220),
            "degree": _text(row.get("degree"), 160),
            "stream": _text(row.get("stream"), 180),
            "start_year": _year(row.get("start_year")),
            "end_year": _year(row.get("end_year")),
            "is_current": _boolean(row.get("is_current")),
            "grade_type": _text(row.get("grade_type"), 40),
            "grade_value": _text(row.get("grade_value"), 100),
            "location": _text(row.get("location"), 180),
            "description": _text(row.get("description"), 8000),
        })

    projects = []
    for row in _rows(data.get("projects")):
        if not isinstance(row, dict):
            continue
        custom_fields = []
        for link in _rows(row.get("custom_fields"), 100):
            if not isinstance(link, dict):
                continue
            label = _text(link.get("type"), 100)
            url = _url(link.get("value"), 1200)
            if label and url:
                custom_fields.append({"type": label, "value": url})
        projects.append({
            "name": _text(row.get("name"), 220),
            "description": _text(row.get("description"), 8000),
            "tech_stack": _string_list(row.get("tech_stack"), 180),
            "role": _text(row.get("role"), 160),
            "live_url": _url(row.get("live_url")),
            "github_url": _url(row.get("github_url")),
            "custom_fields": custom_fields,
        })

    experience = []
    for row in _rows(data.get("experience")):
        if not isinstance(row, dict):
            continue
        experience.append({
            "company": _text(row.get("company"), 220),
            "title": _text(row.get("title"), 180),
            "employment_type": _text(row.get("employment_type"), 100),
            "location": _text(row.get("location"), 180),
            "work_mode": _text(row.get("work_mode"), 80),
            "start_date": _text(row.get("start_date"), 20),
            "end_date": _text(row.get("end_date"), 20),
            "is_current": _boolean(row.get("is_current")),
            "description": _text(row.get("description"), 8000),
            "achievements": _string_list(row.get("achievements"), 1000),
            "tech_stack": _string_list(row.get("tech_stack"), 180),
        })

    normalized = {
        "profile": profile,
        "skills": skills,
        "education": education,
        "projects": projects,
        "experience": experience,
    }
    return {section: normalized[section]} if section else normalized


def extract_resume_data(text, links, section=None):
    payload = json.dumps(
        {"resume_text": text, "detected_hyperlinks": links, "requested_section": section},
        ensure_ascii=False,
    )
    result = json_completion(
        [
            {"role": "system", "content": RESUME_EXTRACTION_SYSTEM},
            {"role": "user", "content": payload},
        ],
        temperature=0.0,
        max_tokens=SECTION_MAX_TOKENS.get(section, 5000),
        timeout=90.0,
    )
    try:
        return normalize_resume_data(result, section=section)
    except ValueError:
        current_app.logger.exception("Resume extraction returned an invalid structure.")
        raise
