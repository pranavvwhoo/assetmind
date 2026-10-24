# Academic project report outline

## 1. Abstract
Summarize the problem, prototype approach, four-agent CrewAI workflow, deterministic analytics, and actual evaluation results after running the supplied evaluation. Do not claim results that were not measured.

## 2. Introduction
Introduce IT asset lifecycle reporting and the need to combine reliable numeric inventory summaries with readable interpretation.

## 3. Problem definition
Describe recurring reporting effort, inconsistent spreadsheets, missing values, duplicate identifiers, and the risk of unsupported narrative claims.

## 4. Objectives and scope
Define upload, validation, analysis, multi-agent interpretation, PDF/JSON export, and reproducible evaluation. State that this is a local academic prototype, not an enterprise system.

## 5. Requirements
Summarize functional requirements, permitted technology, file limits, external LLM key requirement, privacy assumptions, and unsupported states.

## 6. System architecture
Use [the architecture diagrams](./architecture.md). Explain the single-process Streamlit design and deterministic data/AI separation.

## 7. CrewAI agent design
Document roles, goals, evidence boundaries, structured Pydantic outputs, and the rule that numeric totals originate from Pandas.

## 8. Workflow and task dependencies
Describe sequential validation, analytics, writing, review, and the bounded revision attempt.

## 9. Implementation
Describe column alias normalization, duplicate/missing checks, unknown-state handling, charting, and ReportLab export.

## 10. User interface
Describe upload/preview, validation, overview charts, report results, downloads, and temporary session history.

## 11. Deployment
Document the Windows setup in [README.md](../README.md) and, if used, the Streamlit-hosted deployment configuration. Never include API keys.

## 12. Testing
Report the exact pytest command, test output, Python/dependency versions, and any skipped/integration checks.

## 13. Evaluation methodology and actual results
Report the synthetic fixture method, deterministic Python-only baseline, measured values from `python -m evaluation.evaluate`, and authorized LLM experiment results only if actually run. Compare latency/cost only when measured.

## 14. Limitations and ethical considerations
Discuss synthetic data, simplistic allocation/retirement rules, external-provider privacy, LLM error/hallucination risks, and absence of persistent storage and manually scored recommendations.

## 15. Future enhancements
Propose stakeholder-validated field mappings, a larger anonymized reference set, human review of recommendation quality, and provider-independent usage accounting.

## 16. Conclusion
Summarize what was built and measured, distinguishing prototype capabilities from unverified deployment or organizational outcomes.

## 17. References
Add checked references for CrewAI, Streamlit, Pandas, Pydantic, ReportLab, and relevant course material in the institution's required citation style. Verify editions, URLs, and access dates before submission.
