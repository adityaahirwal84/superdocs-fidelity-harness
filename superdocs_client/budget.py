"""
Budget guard for SuperDocs operations.

Per the assignment card: "Budget guard: build and prove this in small-sample
mode first; state the cap a full run may spend before you run it, and report
actual spend alongside your results."

An "operation" in SuperDocs terms is billable AI work: editing a section,
creating content, a multi-section edit (counted at one operation per 25
sections touched), etc. Uploads, exports, and downloads are NOT billed
(see https://docs.superdocs.app/account/plans-and-usage). This guard exists
so a runaway loop -- or a well-intentioned "validate my whole document
library" script -- can never spend more than the caller explicitly agreed to
up front.

The API does not expose a way to know the exact cost of a chat turn before
it runs, so this guard works in two layers:

1. A pre-flight ESTIMATE, computed from the number of document chunks the
   edit instruction is likely to touch (any chat turn is a minimum of 1
   operation; large multi-section edits bill one operation per 25 sections).
   If the estimate alone already exceeds the declared cap, the guard refuses
   to start the call at all.

2. Post-hoc ACTUAL tracking, fed by the `usage` block SuperDocs returns on
   every /v1/chat and /v1/chat/async response. Each confirmed spend is
   accumulated; once accumulated spend would exceed the cap, the guard
   raises BudgetExceededError before the next billable call is allowed to
   start, even if the individual call's estimate looks affordable in
   isolation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


class BudgetExceededError(RuntimeError):
    """Raised when a call would push actual or estimated spend past the declared cap."""

    def __init__(self, declared_cap: int, would_be_spend: int, reason: str):
        self.declared_cap = declared_cap
        self.would_be_spend = would_be_spend
        self.reason = reason
        super().__init__(
            f"Budget guard blocked this call: {reason}. "
            f"Declared cap = {declared_cap} operations, would-be spend = {would_be_spend}."
        )


@dataclass
class CostReport:
    """Final cost accounting attached to a validation report."""

    declared_cost_cap: int
    estimated_cost: int
    actual_cost: int = 0
    calls: list = field(default_factory=list)  # list[dict] audit trail

    @property
    def within_budget(self) -> bool:
        return self.actual_cost <= self.declared_cost_cap

    def to_dict(self) -> dict:
        return {
            "declared_cost_cap": self.declared_cost_cap,
            "estimated_cost": self.estimated_cost,
            "actual_cost": self.actual_cost,
            "within_budget": self.within_budget,
            "calls": self.calls,
        }


class BudgetGuard:
    """
    Tracks and enforces a declared operation cost cap across a single harness run.

    Usage:
        guard = BudgetGuard(declared_cap=5)
        guard.check_estimate(guard.estimate_chat_ops(chunk_count=12))
        ... make the API call ...
        guard.record_actual(ops_charged=1, label="edit instruction")
        ...
        report = guard.finalize()
    """

    OPERATIONS_PER_SECTION_BATCH = 25  # SuperDocs bills 1 op per 25 sections edited

    def __init__(self, declared_cap: int):
        if declared_cap <= 0:
            raise ValueError(
                "A cost cap of 0 or less means this run can never spend anything. "
                "Pass a positive integer, e.g. --cost-cap 3."
            )
        self.declared_cap = declared_cap
        self._actual_spend = 0
        self._estimated_spend = 0
        self._calls: list[dict] = []

    @classmethod
    def estimate_chat_ops(cls, chunk_count: int) -> int:
        """
        Estimate the operation cost of a single edit instruction touching
        up to `chunk_count` document sections. A conservative upper bound:
        every chat turn is at least 1 operation, and large multi-section
        edits bill one operation per 25 sections.
        """
        if chunk_count <= 0:
            return 1
        return max(1, math.ceil(chunk_count / cls.OPERATIONS_PER_SECTION_BATCH))

    def check_estimate(self, estimated_ops: int, label: str = "edit instruction") -> None:
        """Raise BudgetExceededError before starting a call whose estimate alone busts the cap."""
        self._estimated_spend += estimated_ops
        projected = self._actual_spend + estimated_ops
        if projected > self.declared_cap:
            raise BudgetExceededError(
                declared_cap=self.declared_cap,
                would_be_spend=projected,
                reason=(
                    f"estimated cost of '{label}' ({estimated_ops} ops) would bring "
                    f"total spend to {projected}, exceeding the declared cap"
                ),
            )

    def record_actual(self, ops_charged: int, label: str, raw_usage: dict | None = None) -> None:
        """Record confirmed spend from a SuperDocs `usage` response block."""
        self._actual_spend += ops_charged
        self._calls.append(
            {
                "label": label,
                "ops_charged": ops_charged,
                "running_total": self._actual_spend,
                "usage": raw_usage or {},
            }
        )
        if self._actual_spend > self.declared_cap:
            raise BudgetExceededError(
                declared_cap=self.declared_cap,
                would_be_spend=self._actual_spend,
                reason=(
                    f"confirmed spend after '{label}' ({self._actual_spend} ops) "
                    "exceeded the declared cap. No further billable calls will be made."
                ),
            )

    def finalize(self) -> CostReport:
        return CostReport(
            declared_cost_cap=self.declared_cap,
            estimated_cost=self._estimated_spend,
            actual_cost=self._actual_spend,
            calls=list(self._calls),
        )
