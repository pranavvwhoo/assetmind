from src.report_generator import generate_pdf


def test_pdf_generation_without_ai_outputs():
    result = generate_pdf({
        "source_name": "inventory.csv",
        "analytics": {
            "total_assets": 2, "allocated_assets": 1, "unallocated_assets": 1,
            "allocation_unknown_assets": 0, "retired_assets": 0, "active_assets": 2,
            "retirement_unknown_assets": 0, "assets_with_missing_information": 0,
            "data_quality_score": 100, "duplicate_identifier_values": 0,
            "allocation_definition": "Blank means unallocated.",
            "retirement_definition": "Only explicit states are counted.",
            "limitations": [],
            "attention_radar": {
                "as_of_date": "2026-10-24",
                "review_threshold": 20,
                "assets_requiring_review": 1,
                "method": "Transparent rule-based score.",
                "signal_counts": {"warranty_expired": 1},
                "review_queue": [{
                    "source_row": 2, "asset_id": "A1", "score": 25, "priority": "Watch",
                    "evidence": ["Warranty expired 2 day(s) ago"],
                    "next_action": "Confirm warranty coverage.",
                }],
            },
        },
    })
    assert result.startswith(b"%PDF")
    assert len(result) > 1000
