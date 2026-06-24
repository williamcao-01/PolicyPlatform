from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from app.domain.models import Finding, Policy, ProcessDefinition, SkillRun, UploadSession
from app.repositories.base import BaseRepository


class PolicyRepository(BaseRepository[Policy]):
    model = Policy

    def find_by_code(self, tenant_id: UUID, code: str) -> Policy | None:
        statement = select(Policy).where(Policy.tenant_id == tenant_id, Policy.code == code)
        return self.session.scalars(statement).first()


class ProcessRepository(BaseRepository[ProcessDefinition]):
    model = ProcessDefinition

    def find_by_code(self, tenant_id: UUID, code: str) -> ProcessDefinition | None:
        statement = select(ProcessDefinition).where(
            ProcessDefinition.tenant_id == tenant_id,
            ProcessDefinition.code == code,
        )
        return self.session.scalars(statement).first()


class FindingRepository(BaseRepository[Finding]):
    model = Finding

    def list_open(self, tenant_id: UUID) -> Sequence[Finding]:
        statement = select(Finding).where(Finding.tenant_id == tenant_id, Finding.closed_at.is_(None))
        return self.session.scalars(statement).all()


class UploadSessionRepository(BaseRepository[UploadSession]):
    model = UploadSession


class SkillRunRepository(BaseRepository[SkillRun]):
    model = SkillRun
