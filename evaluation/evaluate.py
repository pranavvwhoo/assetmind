"""Reproducible, local-only evaluation for deterministic inventory analytics."""

from __future__ import annotations

import json
import argparse
import time
from pathlib import Path
from typing import Any

from src.analytics import calculate_analytics
from src.analytics import audit_numeric_claims
from src.agents import AgentConfigurationError, AgentExecutionError, run_crew
from src.data_processor import load_dataset

ROOT = Path(__file__).resolve().parents[1]


def evaluate() -> dict[str, Any]:
    expected = json.loads((ROOT / "evaluation" / "expected_results.json").read_text(encoding="utf-8"))
    started = time.perf_counter()
    dataset = load_dataset((ROOT / "assets" / "sample_assets.csv").read_bytes(), "sample_assets.csv")
    result = calculate_analytics(dataset)
    elapsed = time.perf_counter() - started
    duplicate_expected = set(expected["duplicate_identifiers"])
    duplicate_found = set(result["duplicate_identifiers"])
    true_positive = len(duplicate_expected & duplicate_found)
    precision = true_positive / len(duplicate_found) if duplicate_found else 1.0
    recall = true_positive / len(duplicate_expected) if duplicate_expected else 1.0
    comparisons = {
        key: {"expected": expected[key], "actual": result[key], "passed": expected[key] == result[key]}
        for key in (
            "total_assets", "allocated_assets", "unallocated_assets", "retired_assets",
            "active_assets", "retirement_unknown_assets", "assets_with_missing_information",
            "data_quality_score", "missing_identifier_rows", "duplicate_identifier_values",
        )
    }
    comparisons["duplicate_precision"] = {"expected": 1.0, "actual": precision, "passed": precision == 1.0}
    comparisons["duplicate_recall"] = {"expected": 1.0, "actual": recall, "passed": recall == 1.0}
    comparisons["missing_values_by_column"] = {
        "expected": expected["missing_values_by_column"],
        "actual": result["missing_values_by_column"],
        "passed": expected["missing_values_by_column"] == result["missing_values_by_column"],
    }
    evaluation_result = {
        "evaluation_type": "deterministic Python baseline; no LLM calls",
        "elapsed_seconds": round(elapsed, 4),
        "comparisons": comparisons,
        "passed": all(item["passed"] for item in comparisons.values()),
        "summary": "All reference-set inventory checks passed." if all(item["passed"] for item in comparisons.values())
                   else "One or more reference-set checks failed.",
        "ai_completion_rate": None,
        "ai_latency_or_cost": "Not measured: no provider-backed run was performed.",
    }
    return evaluation_result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-llm", action="store_true",
        help="Run the real CrewAI workflow (requires GEMINI_API_KEY and may incur provider charges).",
    )
    options = parser.parse_args()
    results = evaluate()
    if options.with_llm:
        dataset = load_dataset((ROOT / "assets" / "sample_assets.csv").read_bytes(), "sample_assets.csv")
        metrics = calculate_analytics(dataset)
        started = time.perf_counter()
        try:
            crew_result = run_crew(metrics, dataset.source_name)
            results["multi_agent"] = {
                "completed": True,
                "elapsed_seconds": round(time.perf_counter() - started, 4),
                "review_passed": crew_result["quality_review"]["passed"],
                "unsupported_numeric_claims": audit_numeric_claims(crew_result["report"], metrics),
                "revision_attempts": crew_result["revision_attempts"],
                "usage_or_cost": "Not reported because reliable provider usage metadata was unavailable.",
            }
        except (AgentConfigurationError, AgentExecutionError) as exc:
            results["multi_agent"] = {
                "completed": False,
                "elapsed_seconds": round(time.perf_counter() - started, 4),
                "error": str(exc),
            }
        results["comparison"] = {
            "baseline_reference_checks_passed": results["passed"],
            "multi_agent_completion": results["multi_agent"]["completed"],
            "reviewer_passed": results["multi_agent"].get("review_passed"),
            "note": "Agent interpretation is advisory; verified numeric output remains the deterministic baseline.",
        }
    print(json.dumps(results, indent=2))
