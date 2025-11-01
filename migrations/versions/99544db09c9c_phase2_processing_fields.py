"""phase2 processing fields

Revision ID: 99544db09c9c
Revises: 94d3bc441d85
Create Date: 2025-11-01 10:14:57.979469

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision: str = '99544db09c9c'
down_revision: Union[str, Sequence[str], None] = '94d3bc441d85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # ------------------------------------------------------------
    # 1) recordings.status enum: ensure required labels & defaults
    # ------------------------------------------------------------
    enum_typname = bind.execute(sa.text("""
      SELECT t.typname
      FROM pg_type t
      JOIN pg_attribute a ON a.atttypid = t.oid
      JOIN pg_class c ON c.oid = a.attrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE c.relname = 'recordings' AND a.attname = 'status'
      LIMIT 1
    """)).scalar()

    if enum_typname:
        for val in ("queued", "processing", "ready", "failed"):
            op.execute(f"ALTER TYPE {enum_typname} ADD VALUE IF NOT EXISTS '{val}';")
        # normalize any bad/null values before enforcing default/NN
        op.execute(sa.text(f"""
          UPDATE recordings
          SET status = 'queued'
          WHERE status IS NULL
             OR status NOT IN ('queued','processing','ready','failed');
        """))
        op.execute(sa.text(f"""
          ALTER TABLE recordings
            ALTER COLUMN status SET DEFAULT 'queued'::{enum_typname},
            ALTER COLUMN status SET NOT NULL;
        """))

    # ------------------------------------------------------------
    # 2) recordings: add Phase 2 processing columns if missing
    #    (timestamps WITHOUT time zone to match your DB)
    # ------------------------------------------------------------
    rec_cols = {c["name"] for c in insp.get_columns("recordings")}

    def add_rec_col_if_missing(name: str, col: sa.Column):
        if name not in rec_cols:
            op.add_column("recordings", col)

    add_rec_col_if_missing("upload_started_at", sa.Column("upload_started_at", sa.DateTime(timezone=False)))
    add_rec_col_if_missing("upload_completed_at", sa.Column("upload_completed_at", sa.DateTime(timezone=False)))
    add_rec_col_if_missing("transcribed_at", sa.Column("transcribed_at", sa.DateTime(timezone=False)))
    add_rec_col_if_missing("summarized_at", sa.Column("summarized_at", sa.DateTime(timezone=False)))
    add_rec_col_if_missing("tasks_extracted_at", sa.Column("tasks_extracted_at", sa.DateTime(timezone=False)))
    add_rec_col_if_missing("r2_object_key", sa.Column("r2_object_key", sa.Text()))
    # keep your existing duration_sec; do NOT add another duration column
    add_rec_col_if_missing("sha256", sa.Column("sha256", sa.Text()))
    add_rec_col_if_missing("error_log", sa.Column("error_log", sa.Text()))

    # ------------------------------------------------------------
    # 3) transcripts: add pipeline fields if missing
    #    (table already exists with PK int, recording_id varchar(40))
    # ------------------------------------------------------------
    if insp.has_table("transcripts"):
        tx_cols = {c["name"] for c in insp.get_columns("transcripts")}
        def add_tx_col_if_missing(name: str, col: sa.Column):
            if name not in tx_cols:
                op.add_column("transcripts", col)

        add_tx_col_if_missing("model", sa.Column("model", sa.Text()))
        add_tx_col_if_missing("language", sa.Column("language", sa.Text()))
        add_tx_col_if_missing("segments", sa.Column("segments", pg.JSONB()))
        add_tx_col_if_missing("cost_usd", sa.Column("cost_usd", sa.Numeric(10, 4)))
    else:
        # If somehow missing (not your case), create with correct FK type
        op.create_table(
            "transcripts",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("recording_id", sa.String(40), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("summary", sa.Text()),
            sa.Column("decisions", sa.Text()),
            sa.Column("questions", sa.Text()),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
            sa.Column("model", sa.Text()),
            sa.Column("language", sa.Text()),
            sa.Column("segments", pg.JSONB()),
            sa.Column("cost_usd", sa.Numeric(10, 4)),
            sa.ForeignKeyConstraint(["recording_id"], ["recordings.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_transcripts_recording_id", "transcripts", ["recording_id"], unique=True)

    # ------------------------------------------------------------
    # 4) tasks: add optional fields + enum (guarded)
    #    (table exists; has confidence already as double precision)
    # ------------------------------------------------------------
    if insp.has_table("tasks"):
        # Create enum if missing
        op.execute("""
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tasksource') THEN
            CREATE TYPE tasksource AS ENUM ('gpt','manual');
          END IF;
        END$$;
        """)
        task_cols = {c["name"] for c in insp.get_columns("tasks")}
        if "source" not in task_cols:
            op.add_column("tasks", sa.Column("source", pg.ENUM("gpt", "manual", name="tasksource"), nullable=False, server_default="gpt"))
        if "offset_start_s" not in task_cols:
            op.add_column("tasks", sa.Column("offset_start_s", sa.Integer()))
        if "offset_end_s" not in task_cols:
            op.add_column("tasks", sa.Column("offset_end_s", sa.Integer()))
        # NOTE: leave existing confidence column as-is (double precision)

    # No "summaries" table: we reuse transcripts.summary for MVP


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # tasks: drop added columns if present (keep enum type around safely)
    if insp.has_table("tasks"):
        task_cols = {c["name"] for c in insp.get_columns("tasks")}
        if "offset_end_s" in task_cols:
            op.drop_column("tasks", "offset_end_s")
        if "offset_start_s" in task_cols:
            op.drop_column("tasks", "offset_start_s")
        if "source" in task_cols:
            op.drop_column("tasks", "source")
        # (we do not drop 'tasksource' type to avoid impacting other DBs)

    # transcripts: drop pipeline fields if present
    if insp.has_table("transcripts"):
        tx_cols = {c["name"] for c in insp.get_columns("transcripts")}
        for name in ("cost_usd", "segments", "language", "model"):
            if name in tx_cols:
                op.drop_column("transcripts", name)

    # recordings: drop only the columns this migration might have added
    if insp.has_table("recordings"):
        rec_cols = {c["name"] for c in insp.get_columns("recordings")}
        for name in (
            "error_log", "sha256", "r2_object_key",
            "tasks_extracted_at", "summarized_at", "transcribed_at",
            "upload_completed_at", "upload_started_at",
        ):
            if name in rec_cols:
                op.drop_column("recordings", name)
