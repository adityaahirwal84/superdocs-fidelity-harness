"""
Professional validation report: summary, assertions executed, passed,
failed, structural differences, validation status, execution time, and
(when the harness ran a live round trip) estimated vs actual cost.

Three output shapes are supported:
  - to_text()      plain, readable console/CI output
  - to_markdown()  for saving alongside a PR or attaching to an issue
  - to_dict()/to_json()  machine-readable, for tooling or dashboards
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from assertions import Status
from validator.engine import ValidationRun
from superdocs_client.budget import CostReport


@dataclass
class ValidationReport:
    original_path: str
    edited_path: str
    generated_at: str
    execution_time_seconds: float
    total_assertions: int
    passed_count: int
    failed_count: int
    overall_status: str
    failures: list[dict]
    all_results: list[dict]
    package_error: str | None = None
    cost: dict | None = None  # populated only for a live `run`, not a pure `validate`

    # -- serialization --------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "summary": {
                "original_document": self.original_path,
                "edited_document": self.edited_path,
                "generated_at": self.generated_at,
                "execution_time_seconds": round(self.execution_time_seconds, 3),
                "validation_status": self.overall_status,
                "assertions_executed": self.total_assertions,
                "assertions_passed": self.passed_count,
                "assertions_failed": self.failed_count,
            },
            "package_error": self.package_error,
            "structural_differences": self.failures,
            "all_assertions": self.all_results,
            "cost": self.cost,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_text(self) -> str:
        lines = []
        lines.append("=" * 72)
        lines.append("SUPERDOCS ROUND-TRIP FIDELITY REPORT")
        lines.append("=" * 72)
        lines.append(f"Original document : {self.original_path}")
        lines.append(f"Edited document   : {self.edited_path}")
        lines.append(f"Generated at      : {self.generated_at}")
        lines.append(f"Execution time    : {self.execution_time_seconds:.3f}s")
        lines.append("")

        if self.package_error:
            lines.append("VALIDATION STATUS: FAIL (could not open document as a valid .docx)")
            lines.append(f"  {self.package_error}")
            return "\n".join(lines)

        lines.append(f"VALIDATION STATUS : {self.overall_status}")
        lines.append(f"Assertions executed: {self.total_assertions}")
        lines.append(f"Passed             : {self.passed_count}")
        lines.append(f"Failed             : {self.failed_count}")
        lines.append("")

        if self.cost:
            lines.append("-" * 72)
            lines.append("BUDGET")
            lines.append("-" * 72)
            lines.append(f"Declared cost cap : {self.cost['declared_cost_cap']} operations")
            lines.append(f"Estimated cost    : {self.cost['estimated_cost']} operations")
            lines.append(f"Actual cost       : {self.cost['actual_cost']} operations")
            lines.append(f"Within budget     : {self.cost['within_budget']}")
            lines.append("")

        if self.failures:
            lines.append("-" * 72)
            lines.append(f"STRUCTURAL DIFFERENCES ({len(self.failures)})")
            lines.append("-" * 72)
            for f in self.failures:
                lines.append(f"[{f['assertion_name']}] {f['section']}")
                lines.append(f"  Element  : {f['element']}")
                lines.append(f"  Expected : {f['expected']}")
                lines.append(f"  Actual   : {f['actual']}")
                if f.get("detail"):
                    lines.append(f"  Detail   : {f['detail']}")
                lines.append(f"  Status   : FAIL")
                lines.append("")
        else:
            lines.append("No structural differences found.")

        return "\n".join(lines)

    def to_markdown(self) -> str:
        lines = []
        lines.append("# SuperDocs Round-trip Fidelity Report")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Original document**: `{self.original_path}`")
        lines.append(f"- **Edited document**: `{self.edited_path}`")
        lines.append(f"- **Generated at**: {self.generated_at}")
        lines.append(f"- **Execution time**: {self.execution_time_seconds:.3f}s")

        if self.package_error:
            lines.append(f"- **Validation status**: FAIL")
            lines.append("")
            lines.append(f"> {self.package_error}")
            return "\n".join(lines)

        status_word = "PASS" if self.overall_status == "PASS" else "FAIL"
        lines.append(f"- **Validation status**: **{status_word}**")
        lines.append(f"- **Assertions executed**: {self.total_assertions}")
        lines.append(f"- **Passed**: {self.passed_count}")
        lines.append(f"- **Failed**: {self.failed_count}")
        lines.append("")

        if self.cost:
            lines.append("## Budget")
            lines.append("")
            lines.append("| Declared cap | Estimated cost | Actual cost | Within budget |")
            lines.append("|---|---|---|---|")
            lines.append(
                f"| {self.cost['declared_cost_cap']} | {self.cost['estimated_cost']} | "
                f"{self.cost['actual_cost']} | {self.cost['within_budget']} |"
            )
            lines.append("")

        lines.append("## Structural Differences")
        lines.append("")
        if not self.failures:
            lines.append("None. Every checked structural element survived the round trip.")
        else:
            lines.append("| Assertion | Section | Element | Expected | Actual |")
            lines.append("|---|---|---|---|---|")
            for f in self.failures:
                exp = f["expected"].replace("|", "\\|").replace("\n", " ")
                act = f["actual"].replace("|", "\\|").replace("\n", " ")
                lines.append(f"| {f['assertion_name']} | {f['section']} | {f['element']} | {exp} | {act} |")
        lines.append("")

        lines.append("## All Assertions")
        lines.append("")
        lines.append("| Assertion | Section | Element | Status |")
        lines.append("|---|---|---|---|")
        for r in self.all_results:
            lines.append(f"| {r['assertion_name']} | {r['section']} | {r['element']} | {r['status']} |")

        return "\n".join(lines)


def build_report(run: ValidationRun, cost: CostReport | None = None) -> ValidationReport:
    all_results = [r.to_dict() for r in run.results]
    failures = [r.to_dict() for r in run.failed]
    return ValidationReport(
        original_path=run.original_path,
        edited_path=run.edited_path,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        execution_time_seconds=run.execution_time_seconds,
        total_assertions=len(run.results),
        passed_count=len(run.passed),
        failed_count=len(run.failed),
        overall_status=run.overall_status.value if not run.package_error else "FAIL",
        failures=failures,
        all_results=all_results,
        package_error=run.package_error,
        cost=cost.to_dict() if cost else None,
    )
