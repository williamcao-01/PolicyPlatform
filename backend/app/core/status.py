from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from app.core.exceptions import InvalidStateTransitionError


class AssetStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class VersionStatus(StrEnum):
    DRAFT = "draft"
    CURRENT = "current"
    HISTORICAL = "historical"
    REVOKED = "revoked"


class FindingStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"
    REJECTED = "rejected"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_CONFIRMATION = "waiting_confirmation"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UploadStatus(StrEnum):
    RECEIVED = "received"
    ANALYZING = "analyzing"
    NEEDS_CONFIRMATION = "needs_confirmation"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SAVED = "saved"


ASSET_TRANSITIONS: Mapping[AssetStatus, frozenset[AssetStatus]] = {
    AssetStatus.DRAFT: frozenset({AssetStatus.ACTIVE, AssetStatus.ARCHIVED, AssetStatus.DELETED}),
    AssetStatus.ACTIVE: frozenset({AssetStatus.ARCHIVED, AssetStatus.DELETED}),
    AssetStatus.ARCHIVED: frozenset({AssetStatus.ACTIVE, AssetStatus.DELETED}),
    AssetStatus.DELETED: frozenset(),
}

VERSION_TRANSITIONS: Mapping[VersionStatus, frozenset[VersionStatus]] = {
    VersionStatus.DRAFT: frozenset({VersionStatus.CURRENT, VersionStatus.REVOKED}),
    VersionStatus.CURRENT: frozenset({VersionStatus.HISTORICAL, VersionStatus.REVOKED}),
    VersionStatus.HISTORICAL: frozenset({VersionStatus.CURRENT, VersionStatus.REVOKED}),
    VersionStatus.REVOKED: frozenset(),
}

FINDING_TRANSITIONS: Mapping[FindingStatus, frozenset[FindingStatus]] = {
    FindingStatus.PENDING_REVIEW: frozenset({FindingStatus.IN_PROGRESS, FindingStatus.CLOSED, FindingStatus.REJECTED}),
    FindingStatus.IN_PROGRESS: frozenset({FindingStatus.PENDING_REVIEW, FindingStatus.CLOSED, FindingStatus.REJECTED}),
    FindingStatus.CLOSED: frozenset({FindingStatus.IN_PROGRESS}),
    FindingStatus.REJECTED: frozenset({FindingStatus.PENDING_REVIEW}),
}

JOB_TRANSITIONS: Mapping[JobStatus, frozenset[JobStatus]] = {
    JobStatus.QUEUED: frozenset({JobStatus.RUNNING, JobStatus.CANCELLED}),
    JobStatus.RUNNING: frozenset(
        {
            JobStatus.WAITING_CONFIRMATION,
            JobStatus.SUCCEEDED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        }
    ),
    JobStatus.WAITING_CONFIRMATION: frozenset({JobStatus.QUEUED, JobStatus.CANCELLED}),
    JobStatus.SUCCEEDED: frozenset(),
    JobStatus.FAILED: frozenset({JobStatus.QUEUED}),
    JobStatus.CANCELLED: frozenset({JobStatus.QUEUED}),
}

UPLOAD_TRANSITIONS: Mapping[UploadStatus, frozenset[UploadStatus]] = {
    UploadStatus.RECEIVED: frozenset({UploadStatus.ANALYZING, UploadStatus.REJECTED}),
    UploadStatus.ANALYZING: frozenset({UploadStatus.NEEDS_CONFIRMATION, UploadStatus.ACCEPTED, UploadStatus.REJECTED}),
    UploadStatus.NEEDS_CONFIRMATION: frozenset({UploadStatus.ACCEPTED, UploadStatus.REJECTED}),
    UploadStatus.ACCEPTED: frozenset({UploadStatus.SAVED, UploadStatus.REJECTED}),
    UploadStatus.REJECTED: frozenset(),
    UploadStatus.SAVED: frozenset(),
}


def ensure_transition[T: StrEnum](
    current: T,
    target: T,
    transitions: Mapping[T, frozenset[T]],
) -> None:
    if current == target:
        return
    if target not in transitions.get(current, frozenset()):
        raise InvalidStateTransitionError(
            f"Cannot transition from {current.value} to {target.value}.",
            metadata={"current": current.value, "target": target.value},
        )
