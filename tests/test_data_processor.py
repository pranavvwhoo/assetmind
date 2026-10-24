from __future__ import annotations

import io

import pandas as pd
import pytest

from src.data_processor import DatasetError, load_dataset, normalize_boolean, normalize_columns


def test_header_normalization_and_unknown_preservation():
    frame = pd.DataFrame({" asset_tracking_ID ": ["A1"], "Extra Field": ["retained"]})
    normalized, recognized, unknown, issues = normalize_columns(frame)
    assert list(normalized.columns) == ["Asset Tracking ID", "Extra Field"]
    assert recognized == ["Asset Tracking ID"]
    assert unknown == ["Extra Field"]
    assert issues == []
    assert normalized.loc[0, "Extra Field"] == "retained"


def test_ambiguous_identifier_mapping_is_not_guessed():
    frame = pd.DataFrame({"Asset ID": ["A1"], "Asset Tracking ID": ["A2"]})
    normalized, _, _, issues = normalize_columns(frame)
    assert "Asset Tracking ID" not in normalized.columns
    assert any("Ambiguous" in issue for issue in issues)
    assert len(normalized.columns) == 2


@pytest.mark.parametrize(
    ("value", "expected"),
    [("true", True), ("YES", True), ("y", True), (1, True), ("false", False), ("no", False), ("0", False), ("maybe", None), ("", None)],
)
def test_boolean_normalization(value, expected):
    assert normalize_boolean(value) is expected


def test_missing_optional_fields_and_duplicate_ids():
    data = b"Asset Tracking ID,Allocated To,Master Status\nA1,user,active\nA1,,retired\n, user,active\n"
    result = load_dataset(data, "assets.csv")
    assert "Category" not in result.frame
    assert result.duplicate_ids == ["a1"]
    assert result.missing_id_rows == 1
    assert len(result.frame) == 3


def test_missing_required_field_is_reported():
    result = load_dataset(b"Description,Category\nLaptop,Computer\n", "assets.csv")
    assert any("Missing required field" in issue for issue in result.validation_issues)


def test_empty_dataset_with_header_is_preserved():
    result = load_dataset(b"Asset Tracking ID,Category\n", "empty.csv")
    assert result.frame.empty
    assert list(result.frame.columns) == ["Asset Tracking ID", "Category"]


def test_malformed_csv_is_a_helpful_error():
    with pytest.raises(DatasetError, match="Could not read"):
        load_dataset(b'Asset Tracking ID,Description\nA1,"broken\n', "bad.csv")


def test_invalid_excel_is_a_helpful_error():
    with pytest.raises(DatasetError, match="Could not read"):
        load_dataset(b"not an excel workbook", "bad.xlsx")


def test_unsupported_extension_and_size_limit():
    with pytest.raises(DatasetError, match="Unsupported file type"):
        load_dataset(b"x", "assets.json")
    with pytest.raises(DatasetError, match="10 MB"):
        load_dataset(b"x" * (10 * 1024 * 1024 + 1), "assets.csv")
