# Evaluation methodology

## Reproduction

Run `python -m pytest -q` for offline unit tests and `python -m evaluation.evaluate` for the synthetic reference-set evaluation. The fixture is stored in `evaluation/expected_results.json`; the evaluation compares asset totals, allocation and retirement counts, missing-information counts per column, missing IDs, duplicate ID values, and duplicate precision/recall.

The baseline is deterministic Python/Pandas processing. It does not call an LLM. Duration is measured locally and will vary by machine. The script deliberately reports provider completion, usage, and cost as unmeasured instead of inventing results.

## Measures and limitations

- Duplicate precision/recall compare case-insensitive duplicate identifiers with the synthetic expected set.
- Missing-field and total correctness are checked against the static fixture.
- Allocation/retirement correctness checks their reference counts and preserves unknown records.
- Unit tests cover CSV/XLSX failure paths, missing optional/required data, empty data, normalized boolean variants, unsupported types, PDF bytes, missing API configuration, structured four-task orchestration, and unsupported numeric claims.
- An authorized real-provider run can record successful completion rate and wall-clock duration. Cost/usage should only be reported when the provider returns reliable usage metadata. No manually reviewed LLM recommendation-quality score is claimed in this prototype; such a score requires a separately reviewed reference set.

Use `python -m evaluation.evaluate --with-llm` only with an authorized provider key to add a real multi-agent run. It records completion, duration, reviewer pass/fail, and numeric-claim audit results alongside the deterministic baseline. Usage/cost remains unmeasured unless CrewAI/provider usage metadata is reliably exposed. Synthetic results are not representative of production inventories, vendor contracts, or organizational outcomes.

## Current prototype verification

The implementation was checked with Python 3.13.14 and CrewAI 1.15.30: 29 offline tests passed, and all deterministic reference checks passed. The synthetic 57-record baseline produced 34 allocated, 23 unallocated, 5 retired, 46 explicitly active, 6 unknown-retirement records, and a 47.4% row-completeness score. No real-provider call was made, so there are no measured AI success, latency, cost, or recommendation-quality results.
