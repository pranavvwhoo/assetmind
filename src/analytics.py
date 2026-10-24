"""Deterministic asset inventory calculations."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import pandas as pd

from src.data_processor import DatasetResult, normalize_boolean

RETIRED_STATUSES = {"retired", "disposed", "decommissioned"}
ACTIVE_STATUSES = {"active", "in service", "deployed", "in use"}
REVIEW_THRESHOLD = 20


def _group_counts(frame: pd.DataFrame, column: str) -> dict[str, int]:
    if column not in frame.columns:
        return {}
    values = frame[column].fillna("Unknown").astype(str).str.strip().replace("", "Unknown")
    return {str(key): int(value) for key, value in values.value_counts(dropna=False).sort_index().items()}


def build_attention_radar(
    frame: pd.DataFrame,
    duplicate_ids: list[str],
    as_of: date | None = None,
) -> dict[str, Any]:
    """Create an explainable, deterministic review queue without inferring asset value or risk."""
    reference_date = as_of or date.today()
    duplicate_set = {value.casefold() for value in duplicate_ids}
    weights = {
        "missing_asset_id": 35,
        "duplicate_asset_id": 40,
        "zombie_asset_flag": 35,
        "retired_but_allocated": 25,
        "retirement_field_conflict": 20,
        "warranty_expired": 25,
        "warranty_due_90_days": 15,
        "missing_core_field": 8,
    }
    queue: list[dict[str, Any]] = []
    signal_counts = {key: 0 for key in weights}
    flagged_count = 0

    for position, (_, row) in enumerate(frame.iterrows(), start=2):
        reasons: list[str] = []
        score = 0

        def add_signal(key: str, description: str) -> None:
            nonlocal score
            score += weights[key]
            signal_counts[key] += 1
            reasons.append(description)

        raw_asset_id = row.get("Asset Tracking ID", "")
        missing_asset_id = pd.isna(raw_asset_id) or not str(raw_asset_id).strip()
        asset_id = "" if missing_asset_id else str(raw_asset_id).strip()
        normalized_id = asset_id.casefold()
        if missing_asset_id:
            add_signal("missing_asset_id", "Asset identifier is missing")
            asset_id = "Missing ID"
        elif normalized_id in duplicate_set:
            add_signal("duplicate_asset_id", "Asset identifier is duplicated")

        if "Zombie Asset" in frame.columns and normalize_boolean(row.get("Zombie Asset")) is True:
            add_signal("zombie_asset_flag", "Zombie Asset is explicitly true")

        status = str(row.get("Master Status", "")).strip().casefold()
        retired_flag = normalize_boolean(row.get("isRetired")) if "isRetired" in frame.columns else None
        is_retired = retired_flag is True or status in RETIRED_STATUSES
        allocated = (
            "Allocated To" in frame.columns
            and not pd.isna(row.get("Allocated To"))
            and bool(str(row.get("Allocated To")).strip())
        )
        if is_retired and allocated:
            add_signal("retired_but_allocated", "Retired asset still has an assignee")
        if retired_flag is False and status in RETIRED_STATUSES:
            add_signal("retirement_field_conflict", "Retirement flag conflicts with retired status")

        if "Warranty Expiry" in frame.columns:
            warranty_value = row.get("Warranty Expiry")
            if not pd.isna(warranty_value) and str(warranty_value).strip():
                warranty_date = pd.to_datetime(warranty_value, errors="coerce", utc=True)
                if not pd.isna(warranty_date):
                    days_left = (warranty_date.date() - reference_date).days
                    if days_left < 0:
                        add_signal("warranty_expired", f"Warranty expired {abs(days_left)} day(s) ago")
                    elif days_left <= 90:
                        add_signal("warranty_due_90_days", f"Warranty expires in {days_left} day(s)")

        missing_fields = []
        for field in ("Category", "Department", "Master Status", "Make", "Model"):
            if field in frame.columns:
                value = row.get(field)
                if pd.isna(value) or not str(value).strip():
                    missing_fields.append(field)
        for field in missing_fields:
            add_signal("missing_core_field", f"{field} is missing")

        score = min(score, 100)
        priority = "Urgent" if score >= 70 else "High" if score >= 40 else "Watch" if score >= REVIEW_THRESHOLD else "Routine"
        if score >= REVIEW_THRESHOLD:
            flagged_count += 1
            queue.append({
                "source_row": position,
                "asset_id": asset_id,
                "score": score,
                "priority": priority,
                "evidence": reasons,
                "next_action": _attention_action(reasons),
            })

    queue.sort(key=lambda item: (-item["score"], item["source_row"]))
    return {
        "as_of_date": reference_date.isoformat(),
        "method": "Transparent rule-based attention score (0-100); it is a review priority, not a financial, security, or failure-risk prediction.",
        "review_threshold": REVIEW_THRESHOLD,
        "assets_requiring_review": flagged_count,
        "priority_counts": {
            priority: sum(1 for item in queue if item["priority"] == priority)
            for priority in ("Urgent", "High", "Watch")
        },
        "signal_counts": {key: count for key, count in signal_counts.items() if count},
        "review_queue": queue[:25],
        "queue_truncated": flagged_count > 25,
        "scoring_weights": weights,
    }


def _attention_action(reasons: list[str]) -> str:
    if any("identifier" in reason.casefold() for reason in reasons):
        return "Verify the asset record and reconcile its identifier."
    if any("warranty" in reason.casefold() for reason in reasons):
        return "Confirm warranty coverage and plan renewal or replacement review."
    if any("retired" in reason.casefold() for reason in reasons):
        return "Reconcile lifecycle status and assignment before further allocation."
    if any("zombie" in reason.casefold() for reason in reasons):
        return "Confirm the asset is still in service and update its lifecycle record."
    return "Complete the missing inventory fields and confirm the record with its owner."


def calculate_analytics(dataset: DatasetResult) -> dict[str, Any]:
    frame = dataset.frame
    count = len(frame)

    if "Allocated To" in frame.columns:
        allocated_mask = frame["Allocated To"].notna() & frame["Allocated To"].astype("string").str.strip().ne("")
        allocated = int(allocated_mask.sum())
        unallocated = count - allocated
        allocation_unknown = 0
        allocation_basis = "non-empty Allocated To means allocated; blank means unallocated"
    else:
        allocated = unallocated = 0
        allocation_unknown = count
        allocation_basis = "unknown because Allocated To is unavailable"

    retired_mask = pd.Series(False, index=frame.index)
    known_retirement_mask = pd.Series(False, index=frame.index)
    if "isRetired" in frame.columns:
        values = frame["isRetired"].map(normalize_boolean)
        retired_mask |= values.eq(True)
        known_retirement_mask |= values.notna()
    if "Master Status" in frame.columns:
        statuses = frame["Master Status"].fillna("").astype(str).str.strip().str.casefold()
        status_retired = statuses.isin(RETIRED_STATUSES)
        status_active = statuses.isin(ACTIVE_STATUSES)
        retired_mask |= status_retired
        known_retirement_mask |= status_retired | status_active
    retired = int(retired_mask.sum())
    active = int((known_retirement_mask & ~retired_mask).sum())
    retirement_unknown = int(count - retired - active)

    if count:
        row_missing = frame.isna() | frame.astype("string").apply(lambda col: col.str.strip().eq(""))
        rows_with_missing = int(row_missing.any(axis=1).sum())
        quality = round(100 * (1 - rows_with_missing / count), 1)
    else:
        rows_with_missing = 0
        quality = 0.0

    missing_by_column = {
        str(column): int((frame[column].isna() | frame[column].astype("string").str.strip().eq("")).sum())
        for column in frame.columns
    }

    duplicate_count = len(dataset.duplicate_ids)
    invalid_boolean_values: dict[str, int] = {}
    for column in ("Zombie Asset", "isRetired"):
        if column in frame.columns:
            invalid_boolean_values[column] = int(frame[column].isna().sum())
    attention_radar = build_attention_radar(frame, dataset.duplicate_ids)

    return {
        "total_assets": count,
        "allocated_assets": allocated,
        "unallocated_assets": unallocated,
        "allocation_unknown_assets": allocation_unknown,
        "retired_assets": retired,
        "active_assets": active,
        "retirement_unknown_assets": retirement_unknown,
        "assets_with_missing_information": rows_with_missing,
        "data_quality_score": quality,
        "missing_values_by_column": missing_by_column,
        "duplicate_identifier_values": duplicate_count,
        "missing_identifier_rows": dataset.missing_id_rows,
        "duplicate_identifiers": dataset.duplicate_ids,
        "invalid_or_missing_boolean_values": invalid_boolean_values,
        "by_category": _group_counts(frame, "Category"),
        "by_department": _group_counts(frame, "Department"),
        "by_status": _group_counts(frame, "Master Status"),
        "recognized_columns": dataset.recognized_columns,
        "unrecognized_columns": dataset.unrecognized_columns,
        "column_issues": dataset.column_issues,
        "validation_issues": dataset.validation_issues,
        "attention_radar": attention_radar,
        "allocation_definition": allocation_basis,
        "retirement_definition": (
            "Retired when isRetired is true or Master Status is retired/disposed/decommissioned; "
            "active only when explicitly false or status is active/in service/deployed/in use; "
            "other records are unknown. Retired takes precedence."
        ),
        "limitations": [
            "Quality score is the percentage of rows with no blank values in the provided columns.",
            "Missing and unrecognized data is reported, not inferred or removed.",
            "Unknown allocation or retirement states are kept separate from confirmed states.",
            "All totals count source rows; duplicate identifiers are flagged and not silently collapsed.",
        ],
        "record_count_basis": "Counts represent source rows, including rows with duplicate identifiers; duplicates are separately flagged.",
    }


def audit_numeric_claims(report: dict[str, Any], analytics: dict[str, Any]) -> list[str]:
    """Check explicit named metric claims in agent prose against deterministic values."""
    expected = {
        "total assets": str(analytics.get("total_assets", "")),
        "allocated assets": str(analytics.get("allocated_assets", "")),
        "unallocated assets": str(analytics.get("unallocated_assets", "")),
        "retired assets": str(analytics.get("retired_assets", "")),
        "active assets": str(analytics.get("active_assets", "")),
        "data quality score": str(analytics.get("data_quality_score", "")),
    }
    text = json_like_report_text(report)
    problems = []
    for label, value in expected.items():
        pattern = re.compile(rf"\b{re.escape(label)}\b\D{{0,30}}(\d+(?:\.\d+)?)\s*%?", re.IGNORECASE)
        for match in pattern.finditer(text):
            claimed = match.group(1)
            if claimed != value:
                problems.append(f"Unsupported numeric claim: {label} is stated as {claimed}; verified value is {value}.")
    return problems


def json_like_report_text(value: Any) -> str:
    """Flatten structured report values for targeted metric-claim checks."""
    if isinstance(value, dict):
        return " ".join(json_like_report_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(json_like_report_text(item) for item in value)
    return str(value)
