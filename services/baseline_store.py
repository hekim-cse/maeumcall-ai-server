from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from math import isfinite, sqrt
from typing import Any, AsyncIterator, Mapping, Protocol
import hashlib
import hmac
import unicodedata

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from core.config import BASELINE_ID_HMAC_SECRET
from core.database import DatabaseConfigurationError, get_session_factory
from core.models import VoiceBaseline, VoiceCalibrationSample, VoiceSubject


class BaselineStoreError(RuntimeError):
    """Raised when persisted voice baseline data cannot be handled safely."""

    code = "VOICE_BASELINE_STORE_FAILED"
    public_message = "음성 기준선 저장소를 처리하지 못했습니다."
    status_code = 500


class BaselineIdentityError(BaselineStoreError):
    code = "VOICE_BASELINE_ID_INVALID"
    public_message = "유효하지 않은 사용자 식별자입니다."
    status_code = 422


class BaselineIdentityConfigurationError(BaselineStoreError):
    code = "VOICE_BASELINE_SECURITY_NOT_CONFIGURED"
    public_message = "음성 기준선 보안 설정이 완료되지 않았습니다."
    status_code = 503


class BaselineDatabaseConfigurationError(BaselineStoreError):
    code = "VOICE_BASELINE_DATABASE_NOT_CONFIGURED"
    public_message = "음성 기준선 데이터베이스 설정이 완료되지 않았습니다."
    status_code = 503


class BaselineMeasurementError(BaselineStoreError):
    code = "VOICE_BASELINE_MEASUREMENT_INVALID"
    public_message = "음성 측정값이 기준선 계약과 일치하지 않습니다."
    status_code = 422


class BaselineRepository(Protocol):
    async def get_baseline(self, user_key: str) -> dict[str, Any] | None: ...

    async def update_welford(
        self, user_key: str, measurement: tuple[float, float, float]
    ) -> dict[str, Any]: ...

    async def append_calibration_sample(
        self, user_key: str, measurement: tuple[float, float, float]
    ) -> dict[str, Any]: ...

    async def finalize_calibration(self, user_key: str) -> dict[str, Any] | None: ...

    async def clear_calibration(self, user_key: str) -> None: ...

    async def delete_subject(self, user_key: str) -> bool: ...

    async def import_baseline(
        self, user_key: str, baseline: Mapping[str, Any]
    ) -> None: ...


def normalize_user_id(user_id: str | None) -> str:
    if not isinstance(user_id, str):
        raise BaselineIdentityError("user_id must be a string")
    normalized = unicodedata.normalize("NFKC", user_id).strip()
    if not normalized:
        raise BaselineIdentityError("user_id must not be empty")
    if len(normalized) > 128:
        raise BaselineIdentityError("user_id must be at most 128 characters")
    if any(unicodedata.category(char).startswith("C") for char in normalized):
        raise BaselineIdentityError("user_id contains control characters")
    return normalized


def pseudonymize_user_id(user_id: str) -> str:
    normalized = normalize_user_id(user_id)
    if len(BASELINE_ID_HMAC_SECRET) < 32:
        raise BaselineIdentityConfigurationError(
            "BASELINE_ID_HMAC_SECRET must contain at least 32 characters"
        )
    digest = hmac.new(
        BASELINE_ID_HMAC_SECRET.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"user_hmac_sha256:{digest}"


def validate_pseudonymous_key(user_key: str) -> str:
    prefix = "user_hmac_sha256:"
    digest = user_key.removeprefix(prefix)
    if not user_key.startswith(prefix) or len(digest) != 64:
        raise BaselineIdentityError("invalid pseudonymous baseline key")
    try:
        int(digest, 16)
    except ValueError as exc:
        raise BaselineIdentityError("invalid pseudonymous baseline key") from exc
    return user_key


def pct(cur: float, base: float) -> float:
    if base == 0:
        raise BaselineMeasurementError("percentage delta requires a non-zero baseline")
    return round((cur - base) / base * 100.0, 3)


def z(cur: float, mean: float, std: float) -> float:
    if std <= 0:
        raise BaselineMeasurementError("z-score requires a positive standard deviation")
    return round((cur - mean) / std, 3)


def extract_measurement(analysis: Mapping[str, Any]) -> tuple[float, float, float]:
    try:
        measurement = (
            float(analysis["pitch"]["mean"]),
            float(analysis["jitter"]["value"]),
            float(analysis["shimmer"]["value"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise BaselineMeasurementError("voice measurement fields are invalid") from exc
    pitch, jitter, shimmer = measurement
    if (
        not all(isfinite(value) for value in measurement)
        or pitch <= 0
        or jitter < 0
        or shimmer < 0
    ):
        raise BaselineMeasurementError("voice measurement values are out of range")
    return measurement


def calculate_welford(
    current: Mapping[str, Any] | None,
    measurement: tuple[float, float, float],
    *,
    measured_at: datetime | None = None,
) -> dict[str, Any]:
    pitch, jitter, shimmer = measurement
    previous = current or {}
    previous_count = int(previous.get("samples", previous.get("n", 0)))
    count = previous_count + 1

    def update(value: float, mean_key: str, m2_key: str) -> tuple[float, float, float]:
        old_mean = float(previous.get(mean_key, 0.0))
        old_m2 = float(previous.get(m2_key, 0.0))
        delta = value - old_mean
        mean = old_mean + delta / count
        m2 = old_m2 + delta * (value - mean)
        std = sqrt(m2 / (count - 1)) if count > 1 else 0.0
        return mean, m2, std

    pitch_mean, pitch_m2, pitch_std = update(pitch, "pitchHz", "pitch_m2")
    jitter_mean, jitter_m2, jitter_std = update(
        jitter, "jitterLocal", "jitter_m2"
    )
    shimmer_mean, shimmer_m2, shimmer_std = update(
        shimmer, "shimmerLocal", "shimmer_m2"
    )
    timestamp = measured_at or datetime.now(timezone.utc)
    return {
        "n": count,
        "pitchHz": round(pitch_mean, 6),
        "pitchStdHz": round(pitch_std, 6),
        "pitch_m2": pitch_m2,
        "jitterLocal": round(jitter_mean, 6),
        "jitterStd": round(jitter_std, 6),
        "jitter_m2": jitter_m2,
        "shimmerLocal": round(shimmer_mean, 6),
        "shimmerStd": round(shimmer_std, 6),
        "shimmer_m2": shimmer_m2,
        "pitchIqrHz": previous.get("pitchIqrHz"),
        "samples": count,
        "ts": int(timestamp.timestamp()),
    }


def validate_imported_baseline(value: Mapping[str, Any]) -> dict[str, Any]:
    try:
        sample_count = int(value.get("samples", value.get("n")))
        normalized = {
            "samples": sample_count,
            "pitchHz": float(value["pitchHz"]),
            "pitchStdHz": float(value.get("pitchStdHz", 0.0)),
            "pitch_m2": float(value.get("pitch_m2", 0.0)),
            "jitterLocal": float(value["jitterLocal"]),
            "jitterStd": float(value.get("jitterStd", 0.0)),
            "jitter_m2": float(value.get("jitter_m2", 0.0)),
            "shimmerLocal": float(value["shimmerLocal"]),
            "shimmerStd": float(value.get("shimmerStd", 0.0)),
            "shimmer_m2": float(value.get("shimmer_m2", 0.0)),
        }
        if value.get("pitchIqrHz") is not None:
            normalized["pitchIqrHz"] = float(value["pitchIqrHz"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BaselineMeasurementError("imported baseline fields are invalid") from exc
    numeric_values = [
        number
        for key, number in normalized.items()
        if key != "samples"
    ]
    if (
        sample_count <= 0
        or not all(isfinite(number) for number in numeric_values)
        or normalized["pitchHz"] <= 0
        or normalized["jitterLocal"] < 0
        or normalized["shimmerLocal"] < 0
        or normalized["pitchStdHz"] < 0
        or normalized["pitch_m2"] < 0
        or normalized["jitterStd"] < 0
        or normalized["jitter_m2"] < 0
        or normalized["shimmerStd"] < 0
        or normalized["shimmer_m2"] < 0
        or normalized.get("pitchIqrHz", 0.0) < 0
    ):
        raise BaselineMeasurementError("imported baseline values are out of range")
    return normalized


class PostgresBaselineRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    @asynccontextmanager
    async def _read_session(self) -> AsyncIterator[AsyncSession]:
        try:
            async with self._session_factory() as session:
                yield session
        except SQLAlchemyError as exc:
            raise BaselineStoreError("PostgreSQL baseline read failed") from exc

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterator[AsyncSession]:
        try:
            async with self._session_factory() as session, session.begin():
                yield session
        except SQLAlchemyError as exc:
            raise BaselineStoreError("PostgreSQL baseline transaction failed") from exc

    async def _lock_subject(self, session: AsyncSession, user_key: str) -> None:
        await session.execute(
            pg_insert(VoiceSubject)
            .values(user_key=user_key)
            .on_conflict_do_nothing(index_elements=[VoiceSubject.user_key])
        )
        await session.execute(
            select(VoiceSubject.user_key)
            .where(VoiceSubject.user_key == user_key)
            .with_for_update()
        )

    @staticmethod
    def _baseline_dict(baseline: VoiceBaseline) -> dict[str, Any]:
        value = {
            "n": baseline.sample_count,
            "pitchHz": baseline.pitch_hz,
            "pitchStdHz": baseline.pitch_std_hz,
            "pitch_m2": baseline.pitch_m2,
            "jitterLocal": baseline.jitter_local,
            "jitterStd": baseline.jitter_std,
            "jitter_m2": baseline.jitter_m2,
            "shimmerLocal": baseline.shimmer_local,
            "shimmerStd": baseline.shimmer_std,
            "shimmer_m2": baseline.shimmer_m2,
            "samples": baseline.sample_count,
            "ts": int(baseline.updated_at.timestamp()),
        }
        if baseline.pitch_iqr_hz is not None:
            value["pitchIqrHz"] = baseline.pitch_iqr_hz
        return value

    async def get_baseline(self, user_key: str) -> dict[str, Any] | None:
        async with self._read_session() as session:
            baseline = await session.get(VoiceBaseline, user_key)
            return self._baseline_dict(baseline) if baseline else None

    async def update_welford(
        self, user_key: str, measurement: tuple[float, float, float]
    ) -> dict[str, Any]:
        async with self._transaction() as session:
            await self._lock_subject(session, user_key)
            baseline = await session.scalar(
                select(VoiceBaseline)
                .where(VoiceBaseline.user_key == user_key)
                .with_for_update()
            )
            current = self._baseline_dict(baseline) if baseline else None
            calculated = calculate_welford(current, measurement)
            if baseline is None:
                baseline = VoiceBaseline(user_key=user_key, sample_count=1)
                session.add(baseline)
            self._apply_baseline(baseline, calculated)
            await session.flush()
            return self._baseline_dict(baseline)

    async def append_calibration_sample(
        self, user_key: str, measurement: tuple[float, float, float]
    ) -> dict[str, Any]:
        pitch, jitter, shimmer = measurement
        async with self._transaction() as session:
            await self._lock_subject(session, user_key)
            session.add(
                VoiceCalibrationSample(
                    user_key=user_key,
                    pitch_hz=pitch,
                    jitter_local=jitter,
                    shimmer_local=shimmer,
                )
            )
            await session.flush()
            aggregate = (
                await session.execute(
                    select(
                        func.count(VoiceCalibrationSample.id),
                        func.avg(VoiceCalibrationSample.pitch_hz),
                        func.avg(VoiceCalibrationSample.jitter_local),
                        func.avg(VoiceCalibrationSample.shimmer_local),
                        func.stddev_samp(VoiceCalibrationSample.pitch_hz),
                        func.stddev_samp(VoiceCalibrationSample.jitter_local),
                        func.stddev_samp(VoiceCalibrationSample.shimmer_local),
                    ).where(VoiceCalibrationSample.user_key == user_key)
                )
            ).one()
            return self._aggregate_dict(aggregate)

    async def finalize_calibration(self, user_key: str) -> dict[str, Any] | None:
        async with self._transaction() as session:
            await self._lock_subject(session, user_key)
            aggregate = (
                await session.execute(
                    select(
                        func.count(VoiceCalibrationSample.id),
                        func.avg(VoiceCalibrationSample.pitch_hz),
                        func.avg(VoiceCalibrationSample.jitter_local),
                        func.avg(VoiceCalibrationSample.shimmer_local),
                        func.stddev_samp(VoiceCalibrationSample.pitch_hz),
                        func.stddev_samp(VoiceCalibrationSample.jitter_local),
                        func.stddev_samp(VoiceCalibrationSample.shimmer_local),
                    ).where(VoiceCalibrationSample.user_key == user_key)
                )
            ).one()
            if int(aggregate[0]) == 0:
                return None
            calculated = self._aggregate_dict(aggregate)
            baseline = await session.get(VoiceBaseline, user_key)
            if baseline is None:
                baseline = VoiceBaseline(user_key=user_key, sample_count=1)
                session.add(baseline)
            self._apply_baseline(baseline, calculated)
            await session.execute(
                delete(VoiceCalibrationSample).where(
                    VoiceCalibrationSample.user_key == user_key
                )
            )
            await session.flush()
            return self._baseline_dict(baseline)

    async def clear_calibration(self, user_key: str) -> None:
        async with self._transaction() as session:
            await self._lock_subject(session, user_key)
            await session.execute(
                delete(VoiceCalibrationSample).where(
                    VoiceCalibrationSample.user_key == user_key
                )
            )

    async def delete_subject(self, user_key: str) -> bool:
        async with self._transaction() as session:
            result = await session.execute(
                delete(VoiceSubject).where(VoiceSubject.user_key == user_key)
            )
            return bool(result.rowcount)

    async def import_baseline(
        self, user_key: str, baseline: Mapping[str, Any]
    ) -> None:
        validated_key = validate_pseudonymous_key(user_key)
        value = validate_imported_baseline(baseline)
        async with self._transaction() as session:
            await self._lock_subject(session, validated_key)
            persisted = await session.get(VoiceBaseline, validated_key)
            if persisted is None:
                persisted = VoiceBaseline(user_key=validated_key, sample_count=1)
                session.add(persisted)
            self._apply_baseline(persisted, value)

    @staticmethod
    def _aggregate_dict(row: Any) -> dict[str, Any]:
        count, pitch, jitter, shimmer, pitch_std, jitter_std, shimmer_std = row
        timestamp = datetime.now(timezone.utc)
        return {
            "n": int(count),
            "pitchHz": float(pitch),
            "pitchStdHz": float(pitch_std or 0.0),
            "pitch_m2": float(pitch_std or 0.0) ** 2 * max(int(count) - 1, 0),
            "jitterLocal": float(jitter),
            "jitterStd": float(jitter_std or 0.0),
            "jitter_m2": float(jitter_std or 0.0) ** 2 * max(int(count) - 1, 0),
            "shimmerLocal": float(shimmer),
            "shimmerStd": float(shimmer_std or 0.0),
            "shimmer_m2": float(shimmer_std or 0.0) ** 2 * max(int(count) - 1, 0),
            "samples": int(count),
            "ts": int(timestamp.timestamp()),
        }

    @staticmethod
    def _apply_baseline(baseline: VoiceBaseline, value: Mapping[str, Any]) -> None:
        baseline.sample_count = int(value["samples"])
        baseline.pitch_hz = float(value["pitchHz"])
        baseline.pitch_std_hz = float(value.get("pitchStdHz", 0.0))
        baseline.pitch_m2 = float(value.get("pitch_m2", 0.0))
        baseline.pitch_iqr_hz = (
            float(value["pitchIqrHz"]) if value.get("pitchIqrHz") is not None else None
        )
        baseline.jitter_local = float(value["jitterLocal"])
        baseline.jitter_std = float(value.get("jitterStd", 0.0))
        baseline.jitter_m2 = float(value.get("jitter_m2", 0.0))
        baseline.shimmer_local = float(value["shimmerLocal"])
        baseline.shimmer_std = float(value.get("shimmerStd", 0.0))
        baseline.shimmer_m2 = float(value.get("shimmer_m2", 0.0))
        baseline.updated_at = datetime.now(timezone.utc)


_repository: BaselineRepository | None = None


def get_baseline_repository() -> BaselineRepository:
    global _repository
    if _repository is None:
        try:
            _repository = PostgresBaselineRepository(get_session_factory())
        except DatabaseConfigurationError as exc:
            raise BaselineDatabaseConfigurationError(str(exc)) from exc
    return _repository


def set_baseline_repository(repository: BaselineRepository | None) -> None:
    """Set the application repository; tests use this boundary for deterministic doubles."""
    global _repository
    _repository = repository


async def get_persisted_baseline(user_id: str) -> dict[str, Any] | None:
    return await get_baseline_repository().get_baseline(
        pseudonymize_user_id(user_id)
    )


async def update_baseline_persisted(
    user_id: str, analysis: Mapping[str, Any]
) -> dict[str, Any]:
    return await get_baseline_repository().update_welford(
        pseudonymize_user_id(user_id), extract_measurement(analysis)
    )


async def append_calib_sample(
    user_id: str, analysis: Mapping[str, Any]
) -> dict[str, Any]:
    return await get_baseline_repository().append_calibration_sample(
        pseudonymize_user_id(user_id), extract_measurement(analysis)
    )


async def clear_calib_cache(user_id: str) -> None:
    await get_baseline_repository().clear_calibration(
        pseudonymize_user_id(user_id)
    )


async def finalize_calibration_simple(user_id: str) -> dict[str, Any]:
    baseline = await get_baseline_repository().finalize_calibration(
        pseudonymize_user_id(user_id)
    )
    if baseline is None:
        return {"ok": False, "error": "no samples"}
    return {"ok": True, "baseline": baseline}


async def delete_baseline(user_id: str) -> dict[str, Any]:
    deleted = await get_baseline_repository().delete_subject(
        pseudonymize_user_id(user_id)
    )
    return {"ok": True, "deleted": deleted}
