from flask import Blueprint, request, jsonify
from ..services.matching import analyze_job
from ..services.document_parser import parse_uploaded_file, DocumentParseError
from ..services.ai import AIServiceError

matcher_bp = Blueprint("job_matcher", __name__)


@matcher_bp.post("")
def match_job():
    uploaded = request.files.get("file")
    description = request.form.get("job_description", "") if request.content_type and request.content_type.startswith("multipart/form-data") else (request.get_json(silent=True) or {}).get("job_description", "")
    if uploaded and uploaded.filename:
        try:
            description = parse_uploaded_file(uploaded)
        except DocumentParseError as exc:
            return jsonify({"error": str(exc)}), 400
    try:
        result = analyze_job(description)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except AIServiceError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception:
        from flask import current_app
        current_app.logger.exception("Job match failed")
        return jsonify({"error": "Could not analyze this job description. Check AI/Qdrant configuration and try again."}), 503
