"""Input loading, column mapping, and deterministic data-quality checks."""

from __future__ import annotations

import io
import re
import zipfile
import csv
from dataclasses import dataclass
from typing import BinaryIO

import pandas as pd

SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "Asset Tracking ID": (
        "asset tracking id", "asset id", "asset identifier", "asset tag",
        "asset number", "tracking id", "tag number",
    ),
    "Parent ID": ("parent id",),
    "Mapping ID": ("mapping id",),
    "Description": ("description", "asset description"),
    "Location": ("location", "site", "office"),
    "Category": ("category", "asset category", "type"),
    "Department": ("department", "business unit"),
    "Entity": ("entity",),
    "Master Status": ("master status", "status", "asset status"),
    "Master Condition": ("master condition", "condition", "asset condition"),
    "Tagging Status": ("tagging status",),
    "Zombie Asset": ("zombie asset",),
    "isRetired": ("isretired", "is retired", "retired"),
    "Allocated To": ("allocated to", "assigned to", "assignee", "user"),
    "Memory": ("memory", "ram"),
    "Storage": ("storage",),
    "Processor": ("processor", "cpu"),
    "Mac Address": ("mac address", "mac"),
    "Make": ("make", "manufacturer"),
    "Model": ("model",),
    "Purchase Date": ("purchase date",),
    "Warranty Expiry": ("warranty expiry", "warranty expiration"),
    "Vendor": ("vendor", "supplier"),
}
REQUIRED_FIELDS = ("Asset Tracking ID",)
BOOLEAN_FIELDS = ("Zombie Asset", "isRetired")
TRUE_VALUES = {"true", "yes", "y", "1", "t"}
FALSE_VALUES = {"false", "no", "n", "0", "f"}


class DatasetError(ValueError):
    """A user-correctable file or dataset issue."""


@dataclass
class DatasetResult:
    frame: pd.DataFrame
    source_name: str
    recognized_columns: list[str]
    unrecognized_columns: list[str]
    column_issues: list[str]
    validation_issues: list[str]
    missing_by_column: dict[str, int]
    duplicate_ids: list[str]
    missing_id_rows: int


def _normalized_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().casefold()).strip()


_ALIAS_LOOKUP = {
    _normalized_name(alias): canonical
    for canonical, aliases in FIELD_ALIASES.items()
    for alias in (canonical, *aliases)
}


def normalize_boolean(value: object) -> bool | None:
    """Return True/False for recognized representations, otherwise None."""
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    normalized = str(value).strip().casefold()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return None


def normalize_columns(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str], list[str]]:
    """Map recognized headers, preserving unknown headers and detecting collisions."""
    original = list(frame.columns)
    normalized_to_original: dict[str, list[object]] = {}
    for column in original:
        normalized_to_original.setdefault(_normalized_name(column), []).append(column)

    issues: list[str] = []
    for normalized, originals in normalized_to_original.items():
        if len(originals) > 1:
            issues.append(f"Column names {originals!r} normalize to the same value ({normalized!r}).")

    mapped: list[str] = []
    original_names: list[str] = []
    recognized: list[str] = []
    unrecognized: list[str] = []
    for column in original:
        original_names.append(str(column).strip() or "Unnamed column")
        canonical = _ALIAS_LOOKUP.get(_normalized_name(column))
        if canonical:
            mapped.append(canonical)
            recognized.append(canonical)
        else:
            name = str(column).strip() or "Unnamed column"
            mapped.append(name)
            unrecognized.append(name)

    canonical_counts = {name: mapped.count(name) for name in set(mapped)}
    ambiguous = {name for name, count in canonical_counts.items() if count > 1}
    if ambiguous:
        issues.append(
            "Ambiguous field mapping was not guessed for: " + ", ".join(sorted(ambiguous)) + "."
        )
        for index, name in enumerate(mapped):
            if name in ambiguous:
                mapped[index] = f"{original_names[index]} [ambiguous mapping]"

    # Make colliding labels unique while retaining every source column for preview and inspection.
    seen: dict[str, int] = {}
    for index, name in enumerate(mapped):
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            mapped[index] = f"{name} [duplicate source column {seen[name]}]"

    result = frame.copy()
    result.columns = mapped
    return result, list(dict.fromkeys(recognized)), unrecognized, issues


def load_dataset(file: BinaryIO | bytes, filename: str) -> DatasetResult:
    """Load and validate CSV/XLSX input without discarding source rows or columns."""
    extension = "." + filename.rsplit(".", 1)[-1].casefold() if "." in filename else ""
    if extension not in SUPPORTED_EXTENSIONS:
        raise DatasetError("Unsupported file type. Upload a CSV or XLSX file.")

    if isinstance(file, bytes):
        content = file
    else:
        content = file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise DatasetError("File exceeds the 10 MB upload limit.")
    if not content:
        raise DatasetError("The uploaded file is empty.")

    try:
        if extension == ".csv":
            try:
                csv_text = content.decode("utf-8-sig")
                rows = list(csv.reader(io.StringIO(csv_text), strict=True))
            except (UnicodeDecodeError, csv.Error) as exc:
                raise DatasetError(f"Could not read {filename}: malformed CSV ({exc}).") from exc
            if rows:
                expected_width = len(rows[0])
                for row_number, row in enumerate(rows[1:], start=2):
                    if row and len(row) != expected_width:
                        raise DatasetError(
                            f"Could not read {filename}: row {row_number} has {len(row)} fields; expected {expected_width}."
                        )
            frame = pd.read_csv(io.BytesIO(content), dtype=object)
        else:
            frame = pd.read_excel(io.BytesIO(content), engine="openpyxl", dtype=object)
    except (UnicodeDecodeError, pd.errors.ParserError, ValueError, OSError, zipfile.BadZipFile) as exc:
        raise DatasetError(f"Could not read {filename}: {exc}") from exc
    if len(frame.columns) == 0:
        raise DatasetError("The file does not contain any columns.")
    if frame.empty:
        # Preserve the header so users can diagnose an empty export.
        normalized, recognized, unrecognized, column_issues = normalize_columns(frame)
        validation = [f"Missing required field: {field}." for field in REQUIRED_FIELDS if field not in normalized]
        return DatasetResult(normalized, filename, recognized, unrecognized, column_issues, validation, {}, [], 0)

    frame, recognized, unrecognized, column_issues = normalize_columns(frame)
    validation: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in frame.columns:
            validation.append(f"Missing required field: {field}. Map an identifier column explicitly.")

    missing_by_column = {
        str(column): int(frame[column].isna().sum() + frame[column].astype("string").str.strip().eq("").sum())
        for column in frame.columns
    }
    id_column = "Asset Tracking ID"
    missing_id_rows = 0
    duplicate_ids: list[str] = []
    if id_column in frame.columns:
        ids = frame[id_column].astype("string").str.strip()
        missing_id_rows = int(ids.isna().sum() + ids.eq("").sum())
        normalized_ids = ids[ids.notna() & ids.ne("")].str.casefold()
        duplicate_ids = sorted(normalized_ids[normalized_ids.duplicated(keep=False)].unique().tolist())
        if missing_id_rows:
            validation.append(f"{missing_id_rows} row(s) have a missing asset identifier.")
        if duplicate_ids:
            validation.append(f"{len(duplicate_ids)} duplicated asset identifier value(s) were detected.")

    for field in BOOLEAN_FIELDS:
        if field in frame.columns:
            frame[field] = frame[field].map(normalize_boolean)

    return DatasetResult(
        frame, filename, recognized, unrecognized, column_issues,
        validation, missing_by_column, duplicate_ids, missing_id_rows,
    )


def inspect_frame(frame: pd.DataFrame, source_name: str = "sample_assets.csv") -> DatasetResult:
    """Apply the same mapping and validation to an in-memory dataframe."""
    buffer = io.BytesIO()
    frame.to_csv(buffer, index=False)
    buffer.seek(0)
    return load_dataset(buffer, source_name.rsplit(".", 1)[0] + ".csv")
