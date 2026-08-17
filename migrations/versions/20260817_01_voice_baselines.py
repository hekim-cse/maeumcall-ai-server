"""create transactional voice baseline storage

Revision ID: 20260817_01
Revises:
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260817_01"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "voice_subjects",
        sa.Column("user_key", sa.String(length=84), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_key"),
    )
    op.create_table(
        "voice_baselines",
        sa.Column("user_key", sa.String(length=84), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("pitch_hz", sa.Float(precision=53), nullable=False),
        sa.Column("pitch_std_hz", sa.Float(precision=53), nullable=False),
        sa.Column("pitch_m2", sa.Float(precision=53), nullable=False),
        sa.Column("pitch_iqr_hz", sa.Float(precision=53), nullable=True),
        sa.Column("jitter_local", sa.Float(precision=53), nullable=False),
        sa.Column("jitter_std", sa.Float(precision=53), nullable=False),
        sa.Column("jitter_m2", sa.Float(precision=53), nullable=False),
        sa.Column("shimmer_local", sa.Float(precision=53), nullable=False),
        sa.Column("shimmer_std", sa.Float(precision=53), nullable=False),
        sa.Column("shimmer_m2", sa.Float(precision=53), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("jitter_local >= 0", name="ck_voice_baseline_jitter_nonnegative"),
        sa.CheckConstraint("jitter_m2 >= 0", name="ck_voice_baseline_jitter_m2"),
        sa.CheckConstraint("jitter_std >= 0", name="ck_voice_baseline_jitter_std"),
        sa.CheckConstraint(
            "pitch_iqr_hz IS NULL OR pitch_iqr_hz >= 0",
            name="ck_voice_baseline_pitch_iqr",
        ),
        sa.CheckConstraint("pitch_m2 >= 0", name="ck_voice_baseline_pitch_m2"),
        sa.CheckConstraint("pitch_hz > 0", name="ck_voice_baseline_pitch_positive"),
        sa.CheckConstraint("pitch_std_hz >= 0", name="ck_voice_baseline_pitch_std"),
        sa.CheckConstraint("sample_count > 0", name="ck_voice_baseline_sample_count"),
        sa.CheckConstraint("shimmer_local >= 0", name="ck_voice_baseline_shimmer_nonnegative"),
        sa.CheckConstraint("shimmer_m2 >= 0", name="ck_voice_baseline_shimmer_m2"),
        sa.CheckConstraint("shimmer_std >= 0", name="ck_voice_baseline_shimmer_std"),
        sa.ForeignKeyConstraint(["user_key"], ["voice_subjects.user_key"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_key"),
    )
    op.create_table(
        "voice_calibration_samples",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_key", sa.String(length=84), nullable=False),
        sa.Column("pitch_hz", sa.Float(precision=53), nullable=False),
        sa.Column("jitter_local", sa.Float(precision=53), nullable=False),
        sa.Column("shimmer_local", sa.Float(precision=53), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("jitter_local >= 0", name="ck_voice_sample_jitter_nonnegative"),
        sa.CheckConstraint("pitch_hz > 0", name="ck_voice_sample_pitch_positive"),
        sa.CheckConstraint("shimmer_local >= 0", name="ck_voice_sample_shimmer_nonnegative"),
        sa.ForeignKeyConstraint(["user_key"], ["voice_subjects.user_key"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_voice_calibration_samples_user_key"),
        "voice_calibration_samples",
        ["user_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_voice_calibration_samples_user_key"),
        table_name="voice_calibration_samples",
    )
    op.drop_table("voice_calibration_samples")
    op.drop_table("voice_baselines")
    op.drop_table("voice_subjects")
