from __future__ import annotations

import pandas as pd

from datetime import date

from src.analytics import audit_numeric_claims, build_attention_radar, calculate_analytics
from src.data_processor import inspect_frame


def test_verified_allocation_retirement_and_quality_metrics():
    frame = pd.DataFrame({
        "Asset Tracking ID": ["A1", "A2", "A3", "A4"],
        "Allocated To": ["user", "", "user2", None],
        "isRetired": ["yes", "no", "unknown", "no"],
        "Master Status": ["retired", "active", "", "in service"],
        "Category": ["Laptop", "Laptop", "Phone", "Phone"],
    })
    result = calculate_analytics(inspect_frame(frame))
    assert result["total_assets"] == 4
    assert result["allocated_assets"] == 2
    assert result["unallocated_assets"] == 2
    assert result["retired_assets"] == 1
    assert result["active_assets"] == 2
    assert result["retirement_unknown_assets"] == 1
    assert result["by_category"] == {"Laptop": 2, "Phone": 2}


def test_unknown_allocation_is_not_reported_as_unallocated_when_column_absent():
    result = calculate_analytics(inspect_frame(pd.DataFrame({"Asset Tracking ID": ["A1", "A2"]})))
    assert result["allocated_assets"] == result["unallocated_assets"] == 0
    assert result["allocation_unknown_assets"] == 2


def test_empty_dataset_metrics_are_zero_without_division_error():
    dataset = inspect_frame(pd.DataFrame(columns=["Asset Tracking ID", "Allocated To"]))
    result = calculate_analytics(dataset)
    assert result["total_assets"] == 0
    assert result["data_quality_score"] == 0


def test_numeric_claim_audit_flags_incorrect_metric_but_allows_exact_claim():
    verified = {"total_assets": 12, "allocated_assets": 7, "unallocated_assets": 5,
                "retired_assets": 2, "active_assets": 8, "data_quality_score": 75.0}
    assert audit_numeric_claims({"executive_summary": "Total assets: 12"}, verified) == []
    problems = audit_numeric_claims({"executive_summary": "Total assets: 15"}, verified)
    assert len(problems) == 1 and "verified value is 12" in problems[0]


def test_attention_radar_explains_high_priority_signals_and_uses_fixed_date():
    frame = pd.DataFrame({
        "Asset Tracking ID": ["DUP", "DUP", "B2", "C3"],
        "Category": ["Laptop", "Laptop", "Phone", None],
        "Department": ["IT", "IT", "Sales", None],
        "Master Status": ["active", "active", "retired", None],
        "isRetired": [False, False, True, None],
        "Zombie Asset": ["yes", "no", "no", None],
        "Allocated To": ["", "", "employee", ""],
        "Warranty Expiry": ["2025-12-31", "2027-01-01", "2027-01-01", "unknown"],
    })
    radar = build_attention_radar(frame, ["dup"], as_of=date(2026, 10, 24))
    assert radar["as_of_date"] == "2026-10-24"
    assert radar["assets_requiring_review"] == 4
    assert radar["review_queue"][0]["asset_id"] == "DUP"
    assert radar["review_queue"][0]["score"] == 100
    assert radar["review_queue"][0]["priority"] == "Urgent"
    assert "Asset identifier is duplicated" in radar["review_queue"][0]["evidence"]
    retired = next(item for item in radar["review_queue"] if item["asset_id"] == "B2")
    assert retired["priority"] == "High"
    assert "Retired asset still has an assignee" in retired["evidence"]
    assert radar["priority_counts"] == {"Urgent": 1, "High": 2, "Watch": 1}


def test_attention_radar_does_not_flag_unknown_warranty_as_expired():
    frame = pd.DataFrame({
        "Asset Tracking ID": ["A1"],
        "Warranty Expiry": ["not a date"],
    })
    radar = build_attention_radar(frame, [], as_of=date(2026, 10, 24))
    assert radar["signal_counts"] == {}
    assert radar["assets_requiring_review"] == 0
