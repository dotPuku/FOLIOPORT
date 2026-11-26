from flask import Blueprint, jsonify
from ..services.portfolio import get_portfolio_bundle
from ..models import Skill

public_bp = Blueprint("public", __name__)


@public_bp.get("/portfolio")
def public_portfolio():
    return jsonify(get_portfolio_bundle(public_only=True))


@public_bp.get("/skill-types")
def public_skill_types():
    types = [row[0] for row in Skill.query.with_entities(Skill.category).distinct().order_by(Skill.category).all() if row[0]]
    return jsonify({"types": types})
