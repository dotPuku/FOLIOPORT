import re
from datetime import datetime
from uuid import uuid4
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from sqlalchemy import select
from ..extensions import db, limiter
from ..models import (
    Education,
    Experience,
    Profile,
    Project,
    ReindexJob,
    ReindexJobItem,
    Skill,
    utcnow,
)
from ..utils.serialization import serialize_profile, serialize_skill, serialize_education, serialize_project, serialize_experience
from ..utils.text import clean_string, safe_list
from ..services.ai import AIServiceError
from ..services.document_parser import DocumentParseError, parse_uploaded_resume
from ..services.resume_import import extract_resume_data
from ..services.rag import clear_index, sync_entity, sync_entities

admin_bp = Blueprint("admin", __name__)
REINDEX_BATCH_SIZE = 5

PROFILE_EDITABLE = {
    "full_name": (160, False), "headline": (220, False), "phone": (40, False), "email": (255, False),
    "github_url": (500, False), "linkedin_url": (500, False), "website_url": (500, False),
    "resume_url": (500, False), "location": (180, False), "objective": (5000, False),
    "preferred_roles": (1000, False), "years_experience": (0, True), "availability": (120, False),
}


def _serialize_reindex_job(job):
    if job.total_entities:
        progress = round(job.processed_entities * 100 / job.total_entities)
    else:
        progress = 100 if job.status == "completed" else 0
    return {
        "id": job.id,
        "status": job.status,
        "total_entities": job.total_entities,
        "processed_entities": job.processed_entities,
        "indexed_chunks": job.indexed_chunks,
        "progress": progress,
        "error": job.error_message or None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def _enqueue_reindex_job():
    active_job = ReindexJob.query.filter(
        ReindexJob.status.in_(("queued", "running"))
    ).order_by(ReindexJob.created_at.desc()).first()
    if active_job:
        return active_job, False

    job = ReindexJob(id=str(uuid4()), status="queued")
    db.session.add(job)
    entities = []
    if db.session.get(Profile, 1) is not None:
        entities.append(("profile", 1))
    for kind, model in (
        ("skill", Skill),
        ("education", Education),
        ("project", Project),
        ("experience", Experience),
    ):
        entity_ids = db.session.scalars(select(model.id).order_by(model.id)).all()
        entities.extend((kind, entity_id) for entity_id in entity_ids)
    db.session.add_all([
        ReindexJobItem(
            job_id=job.id,
            position=position,
            entity_kind=kind,
            entity_id=entity_id,
            status="queued",
        )
        for position, (kind, entity_id) in enumerate(entities)
    ])
    job.total_entities = len(entities)
    db.session.commit()
    return job, True


def _active_reindex_job():
    return ReindexJob.query.filter(
        ReindexJob.status.in_(("queued", "running"))
    ).order_by(ReindexJob.created_at.desc()).first()


def _payload():
    return request.get_json(silent=True) or {}


def _bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _float(value, label):
    try:
        parsed = float(value or 0)
    except (ValueError, TypeError):
        raise ValueError(f"{label} must be a number.")
    if parsed < 0 or parsed > 80:
        raise ValueError(f"{label} must be between 0 and 80.")
    return parsed


def _int_or_none(value, label):
    if value in (None, ""):
        return None
    try:
        year = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"{label} must be a year.")
    if year < 1900 or year > 2200:
        raise ValueError(f"{label} is outside the accepted year range.")
    return year


def _experience_date(value, label):
    text = clean_string(value or "", 20).strip()
    if not text:
        return ""
    for pattern in ("%m/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, pattern).strftime(pattern)
        except ValueError:
            continue
    try:
        return datetime.strptime(text, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        pass
    legacy = re.fullmatch(r"(19\d{2}|20\d{2}|21\d{2})-(0?[1-9]|1[0-2])", text)
    if legacy:
        return f"{int(legacy.group(2)):02d}/{legacy.group(1)}"
    raise ValueError(f"{label} must use MM/YYYY or DD/MM/YYYY.")


def _update(item, fields, body, list_fields=(), float_fields=(), int_fields=(), bool_fields=()):
    for field in fields:
        if field not in body:
            continue
        value = body[field]
        if field in list_fields:
            if value is None:
                value = []
            if isinstance(value, str):
                value = [part.strip() for part in value.split(",") if part.strip()]
            if not isinstance(value, list):
                raise ValueError(f"{field} must be a list.")
            value = value[:100]
            if field in {"tech_stack", "achievements"}:
                value = [clean_string(v, 180) for v in value if str(v).strip()]
            elif field == "custom_fields":
                value = [{"type": clean_string(v.get("type", ""), 100), "value": clean_string(v.get("value", ""), 1200)} for v in value if isinstance(v, dict) and clean_string(v.get("type", ""), 100) and clean_string(v.get("value", ""), 1200)]
        elif field in float_fields:
            value = _float(value, field.replace("_", " "))
        elif field in int_fields:
            value = _int_or_none(value, field.replace("_", " "))
        elif field in bool_fields:
            value = _bool(value)
        elif field in {"start_date", "end_date"} and "company" in fields and "title" in fields:
            value = _experience_date(value, field.replace("_", " "))
        elif value is None:
            value = ""
        elif isinstance(value, str):
            value = clean_string(value, 8000 if field in {"description", "evidence", "objective"} else 2000)
        setattr(item, field, value)


@admin_bp.get("/profile")
@jwt_required()
def get_profile():
    profile = db.session.get(Profile, 1)
    if profile is None:
        profile = Profile(id=1)
        db.session.add(profile)
        db.session.commit()
    return jsonify(serialize_profile(profile))


@admin_bp.patch("/profile")
@jwt_required()
def patch_profile():
    body = _payload()
    key = body.get("key")
    if key == "public_fields":
        allowed = set(PROFILE_EDITABLE.keys())
        values = body.get("value")
        if not isinstance(values, list) or any(item not in allowed for item in values):
            return jsonify({"error": "Invalid public visibility settings."}), 400
        profile = db.session.get(Profile, 1)
        if profile is None:
            profile = Profile(id=1)
            db.session.add(profile)
        profile.public_fields = sorted(set(values))
    else:
        if key not in PROFILE_EDITABLE:
            return jsonify({"error": "Unknown or non-editable profile field."}), 400
        profile = db.session.get(Profile, 1)
        if profile is None:
            profile = Profile(id=1)
            db.session.add(profile)
        limit, numeric = PROFILE_EDITABLE[key]
        try:
            value = _float(body.get("value"), key) if numeric else clean_string(body.get("value", ""), limit)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        setattr(profile, key, value)
        if "is_public" in body:
            permitted = set(profile.public_fields or [])
            if _bool(body.get("is_public")):
                permitted.add(key)
            else:
                permitted.discard(key)
            profile.public_fields = sorted(permitted)
    db.session.commit()
    index = sync_entity("profile", 1)
    return jsonify({"profile": serialize_profile(profile), "index_warning": index.get("warning")})


@admin_bp.post("/resume/parse")
@jwt_required()
@limiter.limit("10 per hour")
def parse_resume():
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Choose a PDF, DOC, or DOCX resume to upload."}), 400
    section = request.form.get("section")
    if section and section not in {"profile", "skills", "education", "projects", "experience"}:
        return jsonify({"error": "Choose a valid resume section."}), 400
    try:
        parsed_file = parse_uploaded_resume(uploaded)
        data = extract_resume_data(parsed_file["text"], parsed_file["links"], section=section or None)
        return jsonify({"data": data})
    except DocumentParseError as exc:
        return jsonify({"error": str(exc)}), 400
    except AIServiceError as exc:
        return jsonify({"error": str(exc)}), 503
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 502


def _import_rows(body, key, max_items=100):
    rows = body.get(key, [])
    if not isinstance(rows, list) or len(rows) > max_items:
        raise ValueError(f"{key.capitalize()} must be a list with no more than {max_items} records.")
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"Every {key} record must be an object.")
    return rows


def _add_import_records(rows, model, fields, required, *, entity_kind, index_entities, list_fields=(), float_fields=(), int_fields=(), bool_fields=()):
    added = 0
    for index, row in enumerate(rows, start=1):
        has_values = any(
            value if isinstance(value, bool) else
            value != 0 if isinstance(value, (int, float)) else
            any(value) if isinstance(value, (list, dict)) else
            bool(str(value or "").strip())
            for value in row.values()
        )
        if not has_values:
            continue
        missing = [field for field in required if not str(row.get(field, "") or "").strip()]
        if missing:
            raise ValueError(f"{model.__name__} record {index} needs {', '.join(missing).replace('_', ' ')}.")
        item = model()
        row = dict(row)
        if _bool(row.get("is_current")):
            if "end_year" in fields:
                row["end_year"] = None
            if "end_date" in fields:
                row["end_date"] = ""
        _update(
            item, fields, row, list_fields=list_fields,
            float_fields=float_fields, int_fields=int_fields,
            bool_fields=bool_fields,
        )
        db.session.add(item)
        index_entities.append((entity_kind, item))
        added += 1
    return added


@admin_bp.post("/resume/import")
@jwt_required()
def import_resume():
    body = _payload()
    profile_data = body.get("profile", {})
    if not isinstance(profile_data, dict):
        return jsonify({"error": "Profile details must be an object."}), 400
    try:
        skills = _import_rows(body, "skills")
        education = _import_rows(body, "education")
        projects = _import_rows(body, "projects")
        experience = _import_rows(body, "experience")
        profile = db.session.get(Profile, 1)
        if profile is None:
            profile = Profile(id=1)
            db.session.add(profile)
        profile_changed = False
        for key, (limit, numeric) in PROFILE_EDITABLE.items():
            if key not in profile_data:
                continue
            value = profile_data[key]
            if numeric:
                if value in (None, ""):
                    continue
                setattr(profile, key, _float(value, key))
                profile_changed = True
            else:
                value = clean_string(value, limit)
                if value:
                    setattr(profile, key, value)
                    profile_changed = True

        index_entities = []
        counts = {
            "skills": _add_import_records(
                skills, Skill, ["name", "category", "level", "years_experience", "evidence"],
                ("name", "category"), entity_kind="skill", index_entities=index_entities,
                float_fields=("years_experience",),
            ),
            "education": _add_import_records(
                education, Education,
                ["institution", "degree", "stream", "start_year", "end_year", "is_current", "grade_type", "grade_value", "location", "description"],
                ("institution",), entity_kind="education", index_entities=index_entities,
                int_fields=("start_year", "end_year"), bool_fields=("is_current",),
            ),
            "projects": _add_import_records(
                projects, Project,
                ["name", "description", "tech_stack", "custom_fields", "role", "live_url", "github_url"],
                ("name",), entity_kind="project", index_entities=index_entities,
                list_fields=("tech_stack", "custom_fields"),
            ),
            "experience": _add_import_records(
                experience, Experience,
                ["company", "title", "employment_type", "location", "work_mode", "start_date", "is_current", "end_date", "description", "achievements", "tech_stack"],
                ("company", "title"), entity_kind="experience", index_entities=index_entities,
                list_fields=("achievements", "tech_stack"),
                bool_fields=("is_current",),
            ),
        }
        db.session.commit()
        if profile_changed:
            index_entities.append(("profile", profile))
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Resume import save failed.")
        return jsonify({"error": "Could not save the reviewed resume details."}), 500

    index_warning = None
    try:
        indexed = sync_entities([(kind, item.id) for kind, item in index_entities])
        index_warning = indexed.get("warning")
    except Exception:
        current_app.logger.exception("Resume details were saved, but Qdrant index sync failed.")
        index_warning = "Resume details were saved, but the search index could not be refreshed. Retry from Admin → Reindex."
    return jsonify({
        "message": "Reviewed resume details saved.",
        "profile": serialize_profile(profile),
        "counts": counts,
        "index_warning": index_warning,
    })


@admin_bp.get("/skill-types")
@jwt_required()
def skill_types():
    values = [row[0] for row in db.session.query(Skill.category).filter(Skill.category.isnot(None)).distinct().order_by(Skill.category).all() if row[0]]
    return jsonify({"types": values})


def _crud_routes(resource, model, serializer, fields, *, required=(), list_fields=(), float_fields=(), int_fields=(), bool_fields=(), entity_kind=None):
    kind = entity_kind or resource.rstrip("s")

    @admin_bp.get(f"/{resource}", endpoint=f"list_{resource}")
    @jwt_required()
    def list_items():
        items = model.query.order_by(model.updated_at.desc()).all()
        return jsonify([serializer(item) for item in items])

    @admin_bp.post(f"/{resource}", endpoint=f"create_{resource}")
    @jwt_required()
    def create_item():
        body = _payload()
        for field in required:
            if not str(body.get(field, "")).strip():
                return jsonify({"error": f"{field.replace('_', ' ').capitalize()} is required."}), 400
        item = model()
        try:
            _update(item, fields, body, list_fields=list_fields, float_fields=float_fields, int_fields=int_fields, bool_fields=bool_fields)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        db.session.add(item)
        db.session.commit()
        index = sync_entity(kind, item.id)
        response = serializer(item)
        response["index_warning"] = index.get("warning")
        return jsonify(response), 201

    @admin_bp.put(f"/{resource}/<int:item_id>", endpoint=f"update_{resource}")
    @jwt_required()
    def update_item(item_id):
        item = db.session.get(model, item_id)
        if item is None:
            return jsonify({"error": f"{resource[:-1].capitalize()} not found."}), 404
        body = _payload()
        try:
            _update(item, fields, body, list_fields=list_fields, float_fields=float_fields, int_fields=int_fields, bool_fields=bool_fields)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        for field in required:
            if not str(getattr(item, field, "") or "").strip():
                return jsonify({"error": f"{field.replace('_', ' ').capitalize()} is required."}), 400
        db.session.commit()
        index = sync_entity(kind, item.id)
        response = serializer(item)
        response["index_warning"] = index.get("warning")
        return jsonify(response)

    @admin_bp.delete(f"/{resource}/<int:item_id>", endpoint=f"delete_{resource}")
    @jwt_required()
    def delete_item(item_id):
        item = db.session.get(model, item_id)
        if item is None:
            return jsonify({"error": f"{resource[:-1].capitalize()} not found."}), 404
        db.session.delete(item)
        db.session.commit()
        index = sync_entity(kind, item_id)
        return jsonify({"message": "Record deleted.", "index_warning": index.get("warning")})

    @admin_bp.delete(f"/{resource}/bulk", endpoint=f"bulk_delete_{resource}")
    @jwt_required()
    def delete_selected_items():
        ids = _payload().get("ids")
        if not isinstance(ids, list) or not ids:
            return jsonify({"error": "Select at least one record to delete."}), 400
        if len(ids) > 500:
            return jsonify({"error": "Select no more than 500 records at a time."}), 400
        if any(isinstance(item_id, bool) or not isinstance(item_id, int) or item_id < 1 for item_id in ids):
            return jsonify({"error": "Record IDs must be positive integers."}), 400
        ids = list(dict.fromkeys(ids))
        items = model.query.filter(model.id.in_(ids)).all()
        if len(items) != len(ids):
            return jsonify({"error": "One or more selected records no longer exist. Refresh the list and try again."}), 404
        try:
            for item in items:
                db.session.delete(item)
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Bulk delete failed for selected %s.", resource)
            return jsonify({"error": f"Could not delete the selected {resource} records."}), 500
        index_warning = None
        try:
            indexed = sync_entities([(kind, item_id) for item_id in ids])
            index_warning = indexed.get("warning")
        except Exception:
            current_app.logger.exception("Selected %s were deleted, but Qdrant index sync failed.", resource)
            index_warning = "Records were deleted, but the search index could not be refreshed. Retry from Admin → Reindex."
        return jsonify({
            "message": f"Deleted {len(ids)} selected {resource} record(s).",
            "deleted": len(ids),
            "index_warning": index_warning,
        })

    @admin_bp.delete(f"/{resource}", endpoint=f"delete_all_{resource}")
    @jwt_required()
    def delete_all_items():
        try:
            deleted = model.query.delete(synchronize_session=False)
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Bulk delete failed for %s.", resource)
            return jsonify({"error": f"Could not delete all {resource} records."}), 500
        index_warning = None
        job = None
        try:
            job, _ = _enqueue_reindex_job()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Records were deleted from %s, but the reindex job could not be queued.", resource)
            index_warning = "Records were deleted, but the search index refresh could not be queued. Retry from Admin → Rebuild index."
        return jsonify({
            "message": f"Deleted {deleted} {resource} record(s).",
            "deleted": deleted,
            "index_warning": index_warning,
            "reindex_job": _serialize_reindex_job(job) if job else None,
        })


_crud_routes("skills", Skill, serialize_skill,
             ["name", "category", "level", "years_experience", "evidence"],
             required=("name", "category"), float_fields=("years_experience",))
_crud_routes("education", Education, serialize_education,
             ["institution", "degree", "stream", "start_year", "end_year", "is_current", "grade_type", "grade_value", "location", "description"],
             required=("institution",), int_fields=("start_year", "end_year"), bool_fields=("is_current",), entity_kind="education")
_crud_routes("projects", Project, serialize_project,
             ["name", "description", "tech_stack", "custom_fields", "role", "live_url", "github_url"],
             required=("name",), list_fields=("tech_stack", "custom_fields"), entity_kind="project")
_crud_routes("experience", Experience, serialize_experience,
             ["company", "title", "employment_type", "location", "work_mode", "start_date", "is_current", "end_date", "description", "achievements", "tech_stack"],
             required=("company", "title"), list_fields=("achievements", "tech_stack"), bool_fields=("is_current",), entity_kind="experience")


@admin_bp.post("/reindex")
@jwt_required()
def run_reindex():
    try:
        job, created = _enqueue_reindex_job()
        return jsonify({
            "message": "Reindex job queued." if created else "An existing reindex job is already active.",
            "job": _serialize_reindex_job(job),
            "batch_size": REINDEX_BATCH_SIZE,
        }), 202 if created else 200
    except Exception as exc:
        current_app.logger.exception("Manual vector reindex failed")
        return jsonify({"error": "Could not queue a search index rebuild."}), 503


@admin_bp.get("/reindex/jobs/active")
@jwt_required()
def active_reindex_job():
    job = _active_reindex_job()
    return jsonify({
        "job": _serialize_reindex_job(job) if job else None,
        "batch_size": REINDEX_BATCH_SIZE,
    })


@admin_bp.get("/reindex/jobs/<string:job_id>")
@jwt_required()
def get_reindex_job(job_id):
    job = db.session.get(ReindexJob, job_id)
    if job is None:
        return jsonify({"error": "Reindex job not found."}), 404
    return jsonify({"job": _serialize_reindex_job(job)})


@admin_bp.post("/reindex/jobs/<string:job_id>/process")
@jwt_required()
@limiter.limit("30 per minute")
def process_reindex_job(job_id):
    job = db.session.execute(
        select(ReindexJob).where(ReindexJob.id == job_id).with_for_update()
    ).scalar_one_or_none()
    if job is None:
        return jsonify({"error": "Reindex job not found."}), 404
    if job.status in {"completed", "failed"}:
        return jsonify({"job": _serialize_reindex_job(job), "batch_size": REINDEX_BATCH_SIZE})

    try:
        if not job.initialized:
            job.status = "running"
            job.started_at = utcnow()
            clear_index()
            job.initialized = True

        items = db.session.execute(
            select(ReindexJobItem)
            .where(
                ReindexJobItem.job_id == job.id,
                ReindexJobItem.status == "queued",
            )
            .order_by(ReindexJobItem.position)
            .limit(REINDEX_BATCH_SIZE)
            .with_for_update()
        ).scalars().all()

        if items:
            result = sync_entities([
                (item.entity_kind, item.entity_id)
                for item in items
            ])
            if result.get("warning"):
                raise RuntimeError(result["warning"])
            for item in items:
                item.status = "completed"
            job.processed_entities += len(items)
            job.indexed_chunks += result.get("indexed", 0)

        if job.processed_entities >= job.total_entities:
            job.status = "completed"
            job.finished_at = utcnow()
        else:
            job.status = "running"
        db.session.commit()
        return jsonify({"job": _serialize_reindex_job(job), "batch_size": REINDEX_BATCH_SIZE})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Reindex job %s failed while processing a batch.", job_id)
        failed_job = db.session.get(ReindexJob, job_id)
        if failed_job:
            failed_job.status = "failed"
            failed_job.error_message = (
                "The search index rebuild failed. Check Qdrant connectivity and the embedding model configuration."
            )
            failed_job.finished_at = utcnow()
            db.session.commit()
            return jsonify({
                "error": failed_job.error_message,
                "job": _serialize_reindex_job(failed_job),
            }), 503
        return jsonify({"error": "The reindex job could not be updated after a failure."}), 503
