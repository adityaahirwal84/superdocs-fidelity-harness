"""Unit tests for the budget guard -- pure logic, no network, no live key."""

from __future__ import annotations

import pytest

from superdocs_client.budget import BudgetGuard, BudgetExceededError


def test_estimate_chat_ops_small_document_is_one_operation():
    assert BudgetGuard.estimate_chat_ops(chunk_count=3) == 1


def test_estimate_chat_ops_scales_by_25_sections():
    assert BudgetGuard.estimate_chat_ops(chunk_count=50) == 2
    assert BudgetGuard.estimate_chat_ops(chunk_count=26) == 2
    assert BudgetGuard.estimate_chat_ops(chunk_count=25) == 1


def test_zero_or_negative_cap_is_rejected():
    with pytest.raises(ValueError):
        BudgetGuard(declared_cap=0)
    with pytest.raises(ValueError):
        BudgetGuard(declared_cap=-1)


def test_check_estimate_blocks_before_any_call_when_estimate_exceeds_cap():
    guard = BudgetGuard(declared_cap=1)
    with pytest.raises(BudgetExceededError):
        guard.check_estimate(estimated_ops=2, label="huge edit")


def test_check_estimate_allows_call_within_cap():
    guard = BudgetGuard(declared_cap=3)
    guard.check_estimate(estimated_ops=2, label="ok edit")  # should not raise


def test_record_actual_accumulates_and_blocks_once_cap_exceeded():
    guard = BudgetGuard(declared_cap=2)
    guard.record_actual(ops_charged=1, label="first edit")
    with pytest.raises(BudgetExceededError):
        guard.record_actual(ops_charged=2, label="second edit")


def test_finalize_reports_declared_estimated_and_actual_cost():
    guard = BudgetGuard(declared_cap=5)
    guard.check_estimate(estimated_ops=1, label="edit 1")
    guard.record_actual(ops_charged=1, label="edit 1", raw_usage={"ops_charged": 1})
    report = guard.finalize()

    assert report.declared_cost_cap == 5
    assert report.estimated_cost == 1
    assert report.actual_cost == 1
    assert report.within_budget is True
    assert len(report.calls) == 1
