# CrewAI IT Asset Report Generator

Academic prototype: **Design, Development, Deployment and Evaluation of a CrewAI-Based Multi-Agent System for Automated IT Asset Report Generation**.

This local Streamlit application loads CSV/XLSX inventory data, calculates authoritative metrics with Pandas, runs four sequential CrewAI agents for evidence-based interpretation and review, and creates downloadable PDF and JSON results. `assets/sample_assets.csv` is synthetic and contains intentional quality issues.

## Live demo

The deployed app is available at [assetmind-ai-pranavvwhoo.streamlit.app](https://assetmind-ai-pranavvwhoo.streamlit.app/). The requested `assetmind-ai` subdomain was already taken, so Streamlit assigned this available owner-specific name. Add `GEMINI_API_KEY` under the app's **Manage app → Settings → Secrets** to enable provider-backed agent reports. Never put the key in GitHub or share it in chat. Without this secret, the deployed dashboard and deterministic analysis still work.

## What's distinctive: Asset Attention Radar

Every analysis includes a deterministic, explainable review queue that identifies records worth a human follow-up: duplicate or missing identifiers, explicit zombie flags, retired-but-assigned assets, conflicting retirement fields, expired/soon-to-expire warranties, and selected missing inventory fields. Each row shows its source row, score, evidence signals, and a suggested next action. The PDF includes the summary, signal counts, and highest-priority queue; JSON contains the structured details. Individual record IDs stay out of the Gemini prompt.

Scores are bounded from 0–100 and prioritized as Urgent (70+), High (40–69), Watch (20–39), or Routine (<20); only 20+ appears in the queue, which displays at most 25 highest-scoring records. Weights and the report date are shown to make the score auditable. This is a review-priority heuristic—not a prediction of financial, cyber-security, or hardware-failure risk—and should not replace an asset owner's validation.

## Requirements

- Python 3.11 or 3.12 recommended (the current project dependencies also target recent Python 3 releases).
- A Google AI Studio Gemini API key is required only to run the real AI report workflow. CrewAI uses its native Google Gen AI provider.
- Uploads are limited to 10 MB. Do not upload employee or company-confidential data to an external LLM unless authorized.

## Windows PowerShell setup

Run these commands from the project folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
streamlit run app.py
```

Create a Gemini API key at [Google AI Studio](https://aistudio.google.com/app/apikey). Set `GEMINI_API_KEY` in `.env`; `GEMINI_MODEL` is optional and defaults to `gemini/gemini-2.5-flash`. `requirements.txt` installs CrewAI's supported Google Gen AI provider extra. Keep `.env` private; it is ignored by Git. The app still performs deterministic analytics without a key, but it reports that CrewAI could not run and does not invent AI results.

## Demonstration

1. Start the app with `streamlit run app.py`.
2. Select **Use synthetic sample dataset** or upload a CSV/XLSX file.
3. Review the preview, field mapping, validation issues, and deterministic dashboard.
4. Configure the API key and click **Generate Report** to execute the four CrewAI agents sequentially.
5. Review agent outputs, task completion records, verified metrics, and reviewer status.
6. Download the PDF and JSON. The session history is temporary and is not backed by a database.

Allocation means a non-empty `Allocated To`; blank means unallocated only when that column exists. Retirement is confirmed by true `isRetired` or retired/disposed/decommissioned status. Active is counted only for explicit false or active/in-service/deployed/in-use states. Other states remain unknown. A retired indicator takes precedence. Data-quality score is the share of rows with no blank cells in the supplied columns; this is a simple completeness indicator, not a certification.

All source columns and rows are retained. Column labels are normalized by case, spaces, and punctuation. Ambiguous aliases are reported and not selected as a required identifier. Unknown columns remain available in the preview and deterministic completeness checks. Duplicate IDs are checked case-insensitively after trimming. Blank/malformed boolean values are unknown, not false.

## Tests and reproducible evaluation

```powershell
python -m pytest -q
python -m evaluation.evaluate
```

Unit tests use a stub CrewAI boundary and do not make paid provider calls. `evaluation.evaluate` measures the deterministic Python-only baseline against the reviewed synthetic reference fixture. To explicitly run a real-provider comparison (requires `GEMINI_API_KEY` and may incur charges), use `python -m evaluation.evaluate --with-llm`. It records completion, elapsed time, reviewer status, and unsupported numeric claims; cost is reported only if reliably available (not currently exposed by this prototype).

Implementation verification in the current environment (Python 3.13.14, CrewAI 1.15.30): `29 passed`; all deterministic fixture checks passed. The 57-row sample has 34 allocated, 23 unallocated, 5 retired, 46 explicitly active, 6 with unknown retirement state, and 47.4% row-completeness score. No real LLM call was made, so multi-agent latency, provider cost, and AI recommendation quality are not reported.

## Deployment

The simplest hosted option is Streamlit Community Cloud: connect this project, select `app.py`, and place `GEMINI_API_KEY` (and optionally `GEMINI_MODEL`) in the app's **Secrets** settings. Do not commit `.env` or secrets. Review the data-sharing implications before enabling an external provider. No public deployment is claimed by this repository.

## Project documents

- [Mentor project report (PDF)](reports/assetmind_project_report.pdf)
- [Mentor report generator](reports/generate_mentor_report.py) — regenerate with `python reports/generate_mentor_report.py`.
- [Architecture](docs/architecture.md)
- [Evaluation methodology](docs/evaluation_methodology.md)
- [Academic report outline](docs/project_report_outline.md)
