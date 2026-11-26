from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import check_password_hash
from ..models import AdminUser


auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    username = str(body.get("username", "")).strip()[:120]
    password = str(body.get("password", ""))
    if not username or not password:
        return jsonify({"error": "Enter your admin username/email and password."}), 400
    user = AdminUser.query.filter((AdminUser.username == username) | (AdminUser.email == username.lower())).first()
    if not user or not user.is_active or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid credentials."}), 401
    token = create_access_token(identity=str(user.id), additional_claims={"role": "admin", "username": user.username})
    return jsonify({"access_token": token, "user": {"id": user.id, "username": user.username, "email": user.email}})


@auth_bp.get("/me")
@jwt_required()
def me():
    user = AdminUser.query.get(int(get_jwt_identity()))
    if not user or not user.is_active:
        return jsonify({"error": "Admin account is not active."}), 401
    return jsonify({"id": user.id, "username": user.username, "email": user.email})
