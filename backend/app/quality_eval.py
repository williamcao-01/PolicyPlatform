from __future__ import annotations

import json
from pathlib import Path

from app.hooks import hooks
from app.models import SkillRunRequest
from app.skill_runner import run_skill
from app.store import store


SCENARIOS = [
    SkillRunRequest(
        skill_id="skill_policy_conflict",
        policy_ids=["policy_purchase", "policy_sub_purchase"],
    ),
    SkillRunRequest(
        skill_id="skill_policy_process_check",
        policy_ids=["policy_purchase"],
        process_ids=["process_purchase"],
    ),
    SkillRunRequest(
        skill_id="skill_no_policy_basis",
        policy_ids=["policy_recruit", "policy_salary"],
        process_ids=["process_recruit"],
    ),
]


def run_quality_eval(output_path: str = "backend/quality-eval-result.json") -> dict:
    store.reset()
    hooks.clear()
    results = []
    for scenario in SCENARIOS:
        result = run_skill(scenario)
        findings = [finding.model_dump() for finding in result.findings]
        evidence_count = sum(len(finding["evidence"]) for finding in findings)
        results.append(
            {
                "skill_id": scenario.skill_id,
                "finding_count": len(findings),
                "evidence_count": evidence_count,
                "severity_distribution": {
                    severity: sum(1 for finding in findings if finding["severity"] == severity)
                    for severity in ["low", "medium", "high", "critical"]
                },
                "findings": findings,
            }
        )
    report = {
        "summary": {
            "scenario_count": len(results),
            "total_findings": sum(item["finding_count"] for item in results),
            "total_evidence": sum(item["evidence_count"] for item in results),
        },
        "results": results,
        "hooks": [event.__dict__ for event in hooks.events],
    }
    path = Path(output_path)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run_quality_eval(), ensure_ascii=False, indent=2))

