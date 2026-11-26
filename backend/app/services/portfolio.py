from flask import current_app
from ..models import Profile, Skill, Education, Project, Experience
from ..utils.text import safe_list

PUBLIC_PROFILE_FIELDS = {
    "full_name", "headline", "phone", "email", "github_url", "linkedin_url", "website_url", "resume_url",
    "location", "objective", "preferred_roles", "availability", "years_experience"
}


def profile_dict(public_only=False):
    profile = db_get_profile()
    if not profile:
        return {}
    fields = [
        "full_name", "headline", "phone", "email", "github_url", "linkedin_url", "website_url",
        "resume_url", "location", "objective", "preferred_roles", "years_experience",
        "availability", "public_fields"
    ]
    result = {name: getattr(profile, name) for name in fields}
    if public_only:
        allowed = set(profile.public_fields or []) & PUBLIC_PROFILE_FIELDS
        result = {key: value for key, value in result.items() if key in allowed}
    return result


def db_get_profile():
    from ..extensions import db
    return db.session.get(Profile, 1)


def get_portfolio_bundle(public_only=False, entity_keys=None):
    from ..extensions import db

    def load_entities(model, kind, query):
        if entity_keys is None:
            return query.all()
        selected_ids = [
            int(entity_id)
            for entity_kind, entity_id in entity_keys
            if entity_kind == kind
        ]
        return query.filter(model.id.in_(selected_ids)).all() if selected_ids else []

    skills = load_entities(
        Skill,
        "skill",
        Skill.query.order_by(Skill.category.asc(), Skill.name.asc()),
    )
    education = load_entities(
        Education,
        "education",
        Education.query.order_by(Education.start_year.desc()),
    )
    projects = load_entities(
        Project,
        "project",
        Project.query.order_by(Project.updated_at.desc()),
    )
    experience = load_entities(
        Experience,
        "experience",
        Experience.query.order_by(Experience.start_date.desc()),
    )
    from ..utils.serialization import serialize_skill, serialize_education, serialize_project, serialize_experience
    profile_requested = entity_keys is None or ("profile", "1") in entity_keys
    profile = profile_dict(public_only=public_only) if profile_requested else {}
    return {
        "profile": profile,
        "skills": [serialize_skill(item) for item in skills],
        "education": [serialize_education(item) for item in education],
        "projects": [serialize_project(item) for item in projects],
        "experience": [serialize_experience(item) for item in experience],
    }


def remove_empty_values(value):
    if isinstance(value, dict):
        cleaned = {
            key: nonempty
            for key, item in value.items()
            if (nonempty := remove_empty_values(item)) is not None
        }
        return cleaned or None
    if isinstance(value, list):
        cleaned = [nonempty for item in value if (nonempty := remove_empty_values(item)) is not None]
        return cleaned or None
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return value


def _has_value(value):
    return value is not None and not (isinstance(value, str) and not value.strip())


def _format_record(kind, title, fields):
    lines = [f"{kind}: {title}"] if _has_value(title) else []
    for label, value in fields:
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(item).strip() for item in value if _has_value(item))
        if _has_value(value):
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def all_searchable_records(public_only=False, entity_keys=None):
    """Flatten every database category into grounded text chunks for retrieval / matching."""
    if entity_keys is not None:
        entity_keys = {(str(kind), str(entity_id)) for kind, entity_id in entity_keys}
    bundle = get_portfolio_bundle(public_only=public_only, entity_keys=entity_keys)
    records = []
    p = bundle["profile"]
    if p:
        public_keys = p.get("public_fields", []) if not public_only else list(p.keys())
        lines = [
            f"{key.replace('_', ' ')}: {p.get(key)}"
            for key in public_keys
            if key != "public_fields" and _has_value(p.get(key))
        ]
        if lines:
            records.append({"kind": "profile", "id": 1, "title": p.get("full_name") or "Profile", "is_public": True, "text": "Professional profile\n" + "\n".join(lines)})
    for category in ("skills", "education", "projects", "experience"):
        for row in bundle[category]:
            if category == "skills":
                title = row.get("name")
                text = _format_record("Skill", title, [
                    ("Category", row.get("category")),
                    ("Level", row.get("level")),
                    ("Years of experience", row.get("years_experience")),
                    ("Evidence", row.get("evidence")),
                ])
            elif category == "education":
                title = row.get("institution")
                years = [str(year) for year in (row.get("start_year"), "Present" if row.get("is_current") else row.get("end_year")) if _has_value(year)]
                grade = " ".join(str(value).strip() for value in (row.get("grade_type"), row.get("grade_value")) if _has_value(value))
                text = _format_record("Education", title, [
                    ("Degree", row.get("degree")),
                    ("Stream", row.get("stream")),
                    ("Years", "–".join(years)),
                    ("Grade", grade),
                    ("Location", row.get("location")),
                    ("Details", row.get("description")),
                ])
            elif category == "projects":
                title = row.get("name")
                custom_fields = [
                    "{}: {}".format(item.get("type", "").strip(), item.get("value", "").strip())
                    for item in safe_list(row.get("custom_fields"))
                    if isinstance(item, dict) and _has_value(item.get("type")) and _has_value(item.get("value"))
                ]
                links = [row.get("live_url"), row.get("github_url")]
                text = _format_record("Project", title, [
                    ("Description", row.get("description")),
                    ("Tech stack", safe_list(row.get("tech_stack"))),
                    ("Role", row.get("role")),
                    ("Links", links),
                    ("Additional links", custom_fields),
                ])
            else:
                title = " at ".join(value for value in (row.get("title"), row.get("company")) if _has_value(value))
                dates = [value for value in (row.get("start_date"), "Present" if row.get("is_current") else row.get("end_date")) if _has_value(value)]
                text = _format_record("Experience", title, [
                    ("Employment type", row.get("employment_type")),
                    ("Location", row.get("location")),
                    ("Work mode", row.get("work_mode")),
                    ("Dates", "–".join(dates)),
                    ("Description", row.get("description")),
                    ("Achievements", safe_list(row.get("achievements"))),
                    ("Tech stack", safe_list(row.get("tech_stack"))),
                ])
            if not text:
                continue
            kind = category.rstrip("s") if category != "experience" else "experience"
            records.append({
                "kind": kind,
                "id": row["id"],
                "title": title if _has_value(title) else kind.capitalize(),
                "is_public": True,
                "text": text,
            })
    return records
