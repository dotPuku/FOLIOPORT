"""Baseline schema, safe to apply to an empty or existing Folioport database."""
from alembic import op
import sqlalchemy as sa


revision = "feae4e9d05ef"
down_revision = None
branch_labels = None
depends_on = None


def _table_is_missing(name):
    return name not in sa.inspect(op.get_bind()).get_table_names()


def upgrade():
    if _table_is_missing("admin_users"):
        op.create_table(
            "admin_users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("username", sa.String(length=80), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_admin_users_email", "admin_users", ["email"], unique=True)
        op.create_index("ix_admin_users_username", "admin_users", ["username"], unique=True)

    if _table_is_missing("education"):
        op.create_table(
            "education",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("institution", sa.String(length=220), nullable=False),
            sa.Column("degree", sa.String(length=160), nullable=True),
            sa.Column("stream", sa.String(length=180), nullable=True),
            sa.Column("start_year", sa.Integer(), nullable=True),
            sa.Column("end_year", sa.Integer(), nullable=True),
            sa.Column("is_current", sa.Boolean(), nullable=False),
            sa.Column("grade_type", sa.String(length=40), nullable=True),
            sa.Column("grade_value", sa.String(length=100), nullable=True),
            sa.Column("location", sa.String(length=180), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_education_start_end", "education", ["start_year", "end_year"])

    if _table_is_missing("experience"):
        op.create_table(
            "experience",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("company", sa.String(length=220), nullable=False),
            sa.Column("title", sa.String(length=180), nullable=False),
            sa.Column("employment_type", sa.String(length=100), nullable=True),
            sa.Column("location", sa.String(length=180), nullable=True),
            sa.Column("work_mode", sa.String(length=80), nullable=True),
            sa.Column("start_date", sa.String(length=20), nullable=True),
            sa.Column("end_date", sa.String(length=20), nullable=True),
            sa.Column("is_current", sa.Boolean(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("achievements", sa.JSON(), nullable=False),
            sa.Column("tech_stack", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_experience_company", "experience", ["company"])

    if _table_is_missing("profile"):
        op.create_table(
            "profile",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("full_name", sa.String(length=160), nullable=False),
            sa.Column("headline", sa.String(length=220), nullable=False),
            sa.Column("phone", sa.String(length=40), nullable=True),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("github_url", sa.String(length=500), nullable=True),
            sa.Column("linkedin_url", sa.String(length=500), nullable=True),
            sa.Column("website_url", sa.String(length=500), nullable=True),
            sa.Column("resume_url", sa.String(length=500), nullable=True),
            sa.Column("location", sa.String(length=180), nullable=True),
            sa.Column("objective", sa.Text(), nullable=True),
            sa.Column("preferred_roles", sa.Text(), nullable=True),
            sa.Column("years_experience", sa.Float(), nullable=False),
            sa.Column("availability", sa.String(length=120), nullable=True),
            sa.Column("public_fields", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if _table_is_missing("projects"):
        op.create_table(
            "projects",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=220), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("tech_stack", sa.JSON(), nullable=False),
            sa.Column("custom_fields", sa.JSON(), nullable=False),
            sa.Column("role", sa.String(length=160), nullable=True),
            sa.Column("live_url", sa.String(length=500), nullable=True),
            sa.Column("github_url", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_projects_name", "projects", ["name"])

    if _table_is_missing("skills"):
        op.create_table(
            "skills",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("category", sa.String(length=100), nullable=False),
            sa.Column("level", sa.String(length=50), nullable=False),
            sa.Column("years_experience", sa.Float(), nullable=False),
            sa.Column("evidence", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_skills_category", "skills", ["category"])
        op.create_index("ix_skills_name", "skills", ["name"])


def downgrade():
    raise RuntimeError(
        "The baseline may represent existing portfolio data and is intentionally non-reversible."
    )
