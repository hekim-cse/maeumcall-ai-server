from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class VoiceSubject(Base):
    __tablename__ = "voice_subjects"

    user_key: Mapped[str] = mapped_column(String(84), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class VoiceBaseline(Base):
    __tablename__ = "voice_baselines"
    __table_args__ = (
        CheckConstraint("sample_count > 0", name="ck_voice_baseline_sample_count"),
        CheckConstraint("pitch_hz > 0", name="ck_voice_baseline_pitch_positive"),
        CheckConstraint("pitch_std_hz >= 0", name="ck_voice_baseline_pitch_std"),
        CheckConstraint("pitch_m2 >= 0", name="ck_voice_baseline_pitch_m2"),
        CheckConstraint(
            "pitch_iqr_hz IS NULL OR pitch_iqr_hz >= 0",
            name="ck_voice_baseline_pitch_iqr",
        ),
        CheckConstraint("jitter_local >= 0", name="ck_voice_baseline_jitter_nonnegative"),
        CheckConstraint("jitter_std >= 0", name="ck_voice_baseline_jitter_std"),
        CheckConstraint("jitter_m2 >= 0", name="ck_voice_baseline_jitter_m2"),
        CheckConstraint("shimmer_local >= 0", name="ck_voice_baseline_shimmer_nonnegative"),
        CheckConstraint("shimmer_std >= 0", name="ck_voice_baseline_shimmer_std"),
        CheckConstraint("shimmer_m2 >= 0", name="ck_voice_baseline_shimmer_m2"),
    )

    user_key: Mapped[str] = mapped_column(
        String(84),
        ForeignKey("voice_subjects.user_key", ondelete="CASCADE"),
        primary_key=True,
    )
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    pitch_hz: Mapped[float] = mapped_column(Float(53), nullable=False)
    pitch_std_hz: Mapped[float] = mapped_column(Float(53), nullable=False, default=0.0)
    pitch_m2: Mapped[float] = mapped_column(Float(53), nullable=False, default=0.0)
    pitch_iqr_hz: Mapped[float | None] = mapped_column(Float(53), nullable=True)
    jitter_local: Mapped[float] = mapped_column(Float(53), nullable=False)
    jitter_std: Mapped[float] = mapped_column(Float(53), nullable=False, default=0.0)
    jitter_m2: Mapped[float] = mapped_column(Float(53), nullable=False, default=0.0)
    shimmer_local: Mapped[float] = mapped_column(Float(53), nullable=False)
    shimmer_std: Mapped[float] = mapped_column(Float(53), nullable=False, default=0.0)
    shimmer_m2: Mapped[float] = mapped_column(Float(53), nullable=False, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class VoiceCalibrationSample(Base):
    __tablename__ = "voice_calibration_samples"
    __table_args__ = (
        CheckConstraint("pitch_hz > 0", name="ck_voice_sample_pitch_positive"),
        CheckConstraint("jitter_local >= 0", name="ck_voice_sample_jitter_nonnegative"),
        CheckConstraint("shimmer_local >= 0", name="ck_voice_sample_shimmer_nonnegative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_key: Mapped[str] = mapped_column(
        String(84),
        ForeignKey("voice_subjects.user_key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pitch_hz: Mapped[float] = mapped_column(Float(53), nullable=False)
    jitter_local: Mapped[float] = mapped_column(Float(53), nullable=False)
    shimmer_local: Mapped[float] = mapped_column(Float(53), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
