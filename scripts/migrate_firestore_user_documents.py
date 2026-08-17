from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import firebase_admin
from firebase_admin import firestore

from core.auth import derive_internal_uid
from core.config import AUTH_SUBJECT_HMAC_SECRET, FIREBASE_PROJECT_ID


@dataclass(frozen=True)
class MigrationTarget:
    kakao_subject: str
    destination_uid: str
    audit_fingerprint: str


def load_targets(path: Path, *, secret: str) -> list[MigrationTarget]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("마이그레이션 대상 파일을 읽을 수 없습니다.") from exc

    if not isinstance(payload, Mapping) or set(payload) != {"kakao_subjects"}:
        raise ValueError("대상 파일은 kakao_subjects 배열만 포함해야 합니다.")
    subjects = payload["kakao_subjects"]
    if not isinstance(subjects, list) or not subjects:
        raise ValueError("kakao_subjects에는 한 명 이상의 실제 대상이 필요합니다.")

    normalized: list[str] = []
    for subject in subjects:
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("모든 kakao_subjects 항목은 비어 있지 않은 문자열이어야 합니다.")
        normalized.append(subject.strip())
    if len(normalized) != len(set(normalized)):
        raise ValueError("kakao_subjects에 중복된 대상이 있습니다.")

    return [
        MigrationTarget(
            kakao_subject=subject,
            destination_uid=derive_internal_uid(subject, secret),
            audit_fingerprint=hashlib.sha256(subject.encode("utf-8")).hexdigest()[:12],
        )
        for subject in normalized
    ]


def classify_documents(
    source: Mapping[str, Any] | None,
    destination: Mapping[str, Any] | None,
) -> str:
    if source is None:
        return "SOURCE_NOT_FOUND"
    if destination is None:
        return "READY"
    if dict(source) == dict(destination):
        return "ALREADY_COPIED"
    return "DESTINATION_CONFLICT"


def _firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        if not FIREBASE_PROJECT_ID.strip():
            raise RuntimeError("FIREBASE_PROJECT_ID가 설정되지 않았습니다.")
        return firebase_admin.initialize_app(
            options={"projectId": FIREBASE_PROJECT_ID.strip()}
        )


def inspect_target(db, target: MigrationTarget) -> str:
    users = db.collection("users")
    source = users.document(target.kakao_subject).get()
    destination = users.document(target.destination_uid).get()
    return classify_documents(
        source.to_dict() if source.exists else None,
        destination.to_dict() if destination.exists else None,
    )


def apply_target(db, target: MigrationTarget) -> str:
    users = db.collection("users")
    source_ref = users.document(target.kakao_subject)
    destination_ref = users.document(target.destination_uid)
    transaction = db.transaction()

    @firestore.transactional
    def migrate_in_transaction(transaction) -> str:
        source = source_ref.get(transaction=transaction)
        destination = destination_ref.get(transaction=transaction)
        source_data = source.to_dict() if source.exists else None
        destination_data = destination.to_dict() if destination.exists else None
        status = classify_documents(source_data, destination_data)

        if status == "READY":
            transaction.set(destination_ref, dict(source_data))
            transaction.delete(source_ref)
            return "MIGRATED"
        if status == "ALREADY_COPIED":
            transaction.delete(source_ref)
            return "LEGACY_REMOVED"
        return status

    return migrate_in_transaction(transaction)


def migrate(targets: Sequence[MigrationTarget], *, apply: bool) -> int:
    app = _firebase_app()
    db = firestore.client(app=app)
    has_blocker = False

    for target in targets:
        status = apply_target(db, target) if apply else inspect_target(db, target)
        print(f"subject_fingerprint={target.audit_fingerprint} status={status}")
        if status in {"SOURCE_NOT_FOUND", "DESTINATION_CONFLICT"}:
            has_blocker = True

    return 2 if has_blocker else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="레거시 Kakao ID Firestore 문서를 내부 Firebase UID로 이관합니다."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="검증 후 트랜잭션 쓰기를 실행합니다. 생략하면 읽기 전용 dry-run입니다.",
    )
    args = parser.parse_args()

    targets = load_targets(
        args.manifest.resolve(), secret=AUTH_SUBJECT_HMAC_SECRET
    )
    return migrate(targets, apply=args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
