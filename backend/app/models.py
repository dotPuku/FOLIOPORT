from datetime import datetime, timezone
from sqlalchemy import UniqueConstraint, Index
from .extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class AdminUser(TimestampMixin, db.Model):
    __tablename__ = "admin_users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class Profile(TimestampMixin, db.Model):
    __tablename__ = "profile"
    id = db.Column(db.Integer, primary_key=True, default=1)
    full_name = db.Column(db.String(160), nullable=False, default="")
    headline = db.Column(db.String(220), nullable=False, default="")
    phone = db.Column(db.String(40), default="")
    email = db.Column(db.String(255), default="")
    github_url = db.Column(db.String(500), default="")
    linkedin_url = db.Column(db.String(500), default="")
    website_url = db.Column(db.String(500), default="")
    resume_url = db.Column(db.String(500), default="")
    location = db.Column(db.String(180), default="")
    objective = db.Column(db.Text, default="")
    preferred_roles = db.Column(db.Text, default="")
    years_experience = db.Column(db.Float, default=0.0, nullable=False)
    availability = db.Column(db.String(120), default="Open to opportunities")
    public_fields = db.Column(db.JSON, default=lambda: [
        "full_name", "headline", "github_url", "linkedin_url", "website_url",
        "resume_url", "location", "objective", "preferred_roles", "availability"
    ], nullable=False)


class Skill(TimestampMixin, db.Model):
    __tablename__ = "skills"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False, index=True)
    category = db.Column(db.String(100), nullable=False, default="Other", index=True)
    level = db.Column(db.String(50), nullable=False, default="Beginner")
    years_experience = db.Column(db.Float, nullable=False, default=0.0)
    evidence = db.Column(db.Text, default="")


class Education(TimestampMixin, db.Model):
    __tablename__ = "education"
    id = db.Column(db.Integer, primary_key=True)
    institution = db.Column(db.String(220), nullable=False)
    degree = db.Column(db.String(160), default="")
    stream = db.Column(db.String(180), default="")
    start_year = db.Column(db.Integer, nullable=True)
    end_year = db.Column(db.Integer, nullable=True)
    is_current = db.Column(db.Boolean, default=False, nullable=False)
    grade_type = db.Column(db.String(40), default="CGPA")
    grade_value = db.Column(db.String(100), default="")
    location = db.Column(db.String(180), default="")
    description = db.Column(db.Text, default="")


class Project(TimestampMixin, db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(220), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False, default="")
    tech_stack = db.Column(db.JSON, default=list, nullable=False)
    custom_fields = db.Column(db.JSON, default=list, nullable=False)  # [{"type":"...", "value":"..."}]
    role = db.Column(db.String(160), default="")
    live_url = db.Column(db.String(500), default="")
    github_url = db.Column(db.String(500), default="")


class Experience(TimestampMixin, db.Model):
    __tablename__ = "experience"
    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(220), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    employment_type = db.Column(db.String(100), default="Internship")
    location = db.Column(db.String(180), default="")
    work_mode = db.Column(db.String(80), default="")
    start_date = db.Column(db.String(20), default="")
    end_date = db.Column(db.String(20), default="")
    is_current = db.Column(db.Boolean, default=False, nullable=False)
    description = db.Column(db.Text, default="")
    achievements = db.Column(db.JSON, default=list, nullable=False)
    tech_stack = db.Column(db.JSON, default=list, nullable=False)


Index("ix_education_start_end", Education.start_year, Education.end_year)
