"""Add bounded reindex queue and safely adopt older portfolio columns."""
from alembic import op
import sqlalchemy as sa


revision = "55e086f63d97"
down_revision = "feae4e9d05ef"
branch_labels = None
depends_on = None


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table):
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _add_column_if_missing(table, column):
    if table in _tables() and column.name not in _columns(table):
        op.add_column(table, column)


def upgrade():
    _add_column_if_missing(
        "skills",
        sa.Column("category", sa.String(length=100), nullable=True),
    )
    if "skills" in _tables():
        skill_columns = _columns("skills")
        if "type" in skill_columns:
            op.execute(sa.text(
                "UPDATE skills SET category = type "
                "WHERE (category IS NULL OR category = '') AND type IS NOT NULL"
            ))
        op.execute(sa.text(
            "UPDATE skills SET category = 'Other' "
            "WHERE category IS NULL OR category = ''"
        ))
        with op.batch_alter_table("skills") as batch_op:
            batch_op.alter_column(
                "category",
                existing_type=sa.String(length=100),
                nullable=False,
            )

    for name, length in (("stream", 180), ("grade_type", 40), ("grade_value", 100)):
        _add_column_if_missing(
            "education",
            sa.Column(name, sa.String(length=length), nullable=True),
        )
    if "education" in _tables():
        education_columns = _columns("education")
        if "field_of_study" in education_columns:
            op.execute(sa.text(
                "UPDATE education SET stream = field_of_study "
                "WHERE (stream IS NULL OR stream = '') AND field_of_study IS NOT NULL"
            ))
        if "grade" in education_columns:
            op.execute(sa.text(
                "UPDATE education SET grade_value = grade "
                "WHERE (grade_value IS NULL OR grade_value = '') AND grade IS NOT NULL"
            ))

    if "reindex_jobs" not in _tables():
        op.create_table(
            "reindex_jobs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("total_entities", sa.Integer(), nullable=False),
            sa.Column("processed_entities", sa.Integer(), nullable=False),
            sa.Column("indexed_chunks", sa.Integer(), nullable=False),
            sa.Column("initialized", sa.Boolean(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_reindex_jobs_status", "reindex_jobs", ["status"])

    if "reindex_job_items" not in _tables():
        op.create_table(
            "reindex_job_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("job_id", sa.String(length=36), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("entity_kind", sa.String(length=20), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.ForeignKeyConstraint(
                ["job_id"],
                ["reindex_jobs.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("job_id", "entity_kind", "entity_id"),
        )
        op.create_index(
            "ix_reindex_job_items_status",
            "reindex_job_items",
            ["job_id", "status", "position"],
        )


def downgrade():
    tables = _tables()
    if "reindex_job_items" in tables:
        op.drop_table("reindex_job_items")
    if "reindex_jobs" in tables:
        op.drop_table("reindex_jobs")
