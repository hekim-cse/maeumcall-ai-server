from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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

            first_sample = await repository.append_calibration_sample(
                user_key, (100.0, 0.01, 0.02)
            )
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

            assert sorted(value["samples"] for value in aggregates) == list(
                range(1, 13)
            )
            baseline = await repository.finalize_calibration(user_key)
            assert baseline is not None
            assert baseline["samples"] == 12
            assert baseline["pitchHz"] == pytest.approx(105.5)
        finally:
            await repository.delete_subject(user_key)
            await engine.dispose()

    asyncio.run(scenario())
