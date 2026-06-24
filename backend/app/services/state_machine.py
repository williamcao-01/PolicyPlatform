from __future__ import annotations

from app.core.status import (
    ASSET_TRANSITIONS,
    FINDING_TRANSITIONS,
    JOB_TRANSITIONS,
    UPLOAD_TRANSITIONS,
    VERSION_TRANSITIONS,
    AssetStatus,
    FindingStatus,
    JobStatus,
    UploadStatus,
    VersionStatus,
    ensure_transition,
)


class StateMachineService:
    def transition_asset(self, current: str, target: str) -> AssetStatus:
        current_status = AssetStatus(current)
        target_status = AssetStatus(target)
        ensure_transition(current_status, target_status, ASSET_TRANSITIONS)
        return target_status

    def transition_version(self, current: str, target: str) -> VersionStatus:
        current_status = VersionStatus(current)
        target_status = VersionStatus(target)
        ensure_transition(current_status, target_status, VERSION_TRANSITIONS)
        return target_status

    def transition_finding(self, current: str, target: str) -> FindingStatus:
        current_status = FindingStatus(current)
        target_status = FindingStatus(target)
        ensure_transition(current_status, target_status, FINDING_TRANSITIONS)
        return target_status

    def transition_job(self, current: str, target: str) -> JobStatus:
        current_status = JobStatus(current)
        target_status = JobStatus(target)
        ensure_transition(current_status, target_status, JOB_TRANSITIONS)
        return target_status

    def transition_upload(self, current: str, target: str) -> UploadStatus:
        current_status = UploadStatus(current)
        target_status = UploadStatus(target)
        ensure_transition(current_status, target_status, UPLOAD_TRANSITIONS)
        return target_status
