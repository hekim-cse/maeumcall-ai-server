from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.models import VoiceSubject
from services.baseline_store import PostgresBaselineRepository

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


def test_postgres_repository_persists_and_finalizes_calibration_samples():
    database_url = os.environ["TEST_DATABASE_URL"]
    user_key = f"user_hmac_sha256:{uuid4().hex}{uuid4().hex}"

    async def scenario() -> None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        repository = PostgresBaselineRepository(
            session_factory=async_sessionmaker(engine, expire_on_commit=False)
        )
        try:
            assert await repository.get_baseline(user_key) is None

            first_sample = await repository.append_calibration_sample(user_key, (100.0, 0.01, 0.02))
            second_sample = await repository.append_calibration_sample(
                user_key, (120.0, 0.03, 0.04)
            )
            assert first_sample["samples"] == 1
            assert second_sample["samples"] == 2

            baseline = await repository.finalize_calibration(user_key)
            assert baseline["samples"] == 2
            assert baseline["pitchHz"] == 110.0
            assert baseline["pitchStdHz"] == pytest.approx(14.142136)
            await repository.clear_calibration(user_key)
            persisted = await repository.get_baseline(user_key)
            assert persisted is not None
            assert persisted["samples"] == 2
            assert persisted["pitchHz"] == 110.0
        finally:
            await repository.delete_subject(user_key)
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_repository_serializes_concurrent_writes_per_user():
    database_url = os.environ["TEST_DATABASE_URL"]
    user_key = f"user_hmac_sha256:{uuid4().hex}{uuid4().hex}"

    async def scenario() -> None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        repository = PostgresBaselineRepository(
            session_factory=async_sessionmaker(engine, expire_on_commit=False)
        )
        try:
            aggregates = await asyncio.gather(
                *[
                    repository.append_calibration_sample(
                        user_key,
                        (100.0 + index, 0.01, 0.02),
                    )
                    for index in range(12)
                ]
            )

            assert sorted(value["samples"] for value in aggregates) == list(range(1, 13))
            baseline = await repository.finalize_calibration(user_key)
            assert baseline is not None
            assert baseline["samples"] == 12
            assert baseline["pitchHz"] == pytest.approx(105.5)
        finally:
            await repository.delete_subject(user_key)
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_batch_import_rolls_back_every_record_on_mid_batch_failure(monkeypatch):
    database_url = os.environ["TEST_DATABASE_URL"]
    first_key, second_key = sorted(
        [
            f"user_hmac_sha256:{uuid4().hex}{uuid4().hex}",
            f"user_hmac_sha256:{uuid4().hex}{uuid4().hex}",
        ]
    )

    async def scenario() -> None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        repository = PostgresBaselineRepository(session_factory=session_factory)
        await repository.import_baseline(
            first_key,
            {
                "samples": 2,
                "pitchHz": 130,
                "jitterLocal": 0.004,
                "shimmerLocal": 0.009,
            },
        )
        original_apply = repository._apply_baseline
        invocation_count = 0

        def fail_on_second_record(baseline, value):
            nonlocal invocation_count
            invocation_count += 1
            if invocation_count == 2:
                raise RuntimeError("injected migration failure")
            original_apply(baseline, value)

        monkeypatch.setattr(repository, "_apply_baseline", fail_on_second_record)
        records = {
            first_key: {
                "samples": 3,
                "pitchHz": 150,
                "jitterLocal": 0.005,
                "shimmerLocal": 0.01,
            },
            second_key: {
                "samples": 4,
                "pitchHz": 160,
                "jitterLocal": 0.006,
                "shimmerLocal": 0.02,
            },
        }
        try:
            with pytest.raises(RuntimeError, match="injected migration failure"):
                await repository.import_baselines(records)

            original = await repository.get_baseline(first_key)
            assert original is not None
            assert original["samples"] == 2
            assert original["pitchHz"] == 130
            assert await repository.get_baseline(second_key) is None
            async with session_factory() as session:
                second_subject_count = await session.scalar(
                    select(func.count())
                    .select_from(VoiceSubject)
                    .where(VoiceSubject.user_key == second_key)
                )
            assert second_subject_count == 0
        finally:
            monkeypatch.setattr(repository, "_apply_baseline", original_apply)
            await repository.delete_subject(first_key)
            await repository.delete_subject(second_key)
            await engine.dispose()

    asyncio.run(scenario())
