from __future__ import annotations

import sys
import types

import pytest

from src.agents import AgentConfigurationError, AgentExecutionError, run_crew
from src.agents import _provider_llm
from src.schemas import AnalyticsInterpretation, QualityAnalysis, ReportDraft, ReviewResult


def test_missing_api_key_fails_clearly(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("src.agents.load_dotenv", lambda: None)
    with pytest.raises(AgentConfigurationError, match="GEMINI_API_KEY"):
        run_crew({"total_assets": 0}, "inventory.csv")


def test_gemini_provider_configuration_uses_gemini_model_and_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini/test-model")
    captured = {}
    fake = types.ModuleType("crewai")

    def llm_factory(**kwargs):
        captured.update(kwargs)
        return object()

    fake.LLM = llm_factory
    monkeypatch.setitem(sys.modules, "crewai", fake)
    _provider_llm()
    assert captured == {
        "model": "gemini/test-model",
        "api_key": "gemini-test-key",
        "temperature": 0,
    }


def test_four_real_crewai_agents_and_structured_outputs_are_orchestrated(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    instances = {"agents": [], "tasks": []}

    class Agent:
        def __init__(self, role, **kwargs):
            self.role = role
            instances["agents"].append(self)

    class Task:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            instances["tasks"].append(self)

    class Crew:
        def __init__(self, agents, tasks, process, task_callback, **kwargs):
            self.agents, self.tasks, self.callback = agents, tasks, task_callback
            assert process == "sequential"

        def kickoff(self):
            schemas = [
                QualityAnalysis(findings=[], correction_actions=[]),
                AnalyticsInterpretation(observations=[], hypotheses_to_investigate=[]),
                ReportDraft(executive_summary="Summary", findings=[], recommendations=[]),
                ReviewResult(passed=True, required_sections_present=["executive summary", "findings", "recommendations"]),
            ]
            outputs = []
            for task, schema in zip(self.tasks, schemas):
                outputs.append(types.SimpleNamespace(pydantic=schema, agent=task.kwargs["agent"]))
                self.callback(outputs[-1])
            return types.SimpleNamespace(tasks_output=outputs)

    fake = types.ModuleType("crewai")
    fake.LLM = lambda **kwargs: object()
    fake.Agent, fake.Task, fake.Crew = Agent, Task, Crew
    fake.Process = types.SimpleNamespace(sequential="sequential")
    monkeypatch.setitem(sys.modules, "crewai", fake)
    result = run_crew({
        "total_assets": 0,
        "attention_radar": {
            "as_of_date": "2026-10-24", "method": "test",
            "review_threshold": 20, "assets_requiring_review": 1,
            "priority_counts": {"Urgent": 1}, "signal_counts": {"duplicate_asset_id": 1},
            "review_queue": [{"asset_id": "SENSITIVE-DEVICE-ID"}],
        },
    }, "inventory.csv")
    assert len(instances["agents"]) == len(instances["tasks"]) == 4
    assert len(result["agent_events"]) == 4
    assert result["quality_review"]["passed"] is True
    assert all(task.kwargs.get("output_pydantic") for task in instances["tasks"])
    assert all("SENSITIVE-DEVICE-ID" not in task.kwargs["description"] for task in instances["tasks"])


def test_unsupported_numeric_agent_claim_forces_failed_review(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    calls = {"count": 0}

    class Agent:
        def __init__(self, role, **kwargs):
            self.role = role

    class Task:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class Crew:
        def __init__(self, tasks, **kwargs):
            self.tasks = tasks

        def kickoff(self):
            calls["count"] += 1
            outputs = [
                QualityAnalysis(), AnalyticsInterpretation(),
                ReportDraft(executive_summary="Total assets: 99", findings=[], recommendations=[]),
                ReviewResult(passed=True),
            ]
            return types.SimpleNamespace(
                tasks_output=[types.SimpleNamespace(pydantic=x) for x in outputs]
            )

    fake = types.ModuleType("crewai")
    fake.LLM = lambda **kwargs: object()
    fake.Agent, fake.Task, fake.Crew = Agent, Task, Crew
    fake.Process = types.SimpleNamespace(sequential="sequential")
    monkeypatch.setitem(sys.modules, "crewai", fake)
    result = run_crew({"total_assets": 3}, "inventory.csv")
    assert calls["count"] == 2
    assert result["quality_review"]["passed"] is False
    assert result["revision_attempts"] == 1


def test_provider_execution_error_is_reported_without_dataset_content(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    class Agent:
        def __init__(self, role, **kwargs):
            self.role = role

    class Task:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class Crew:
        def __init__(self, **kwargs):
            pass

        def kickoff(self):
            raise RuntimeError("provider call failed")

    fake = types.ModuleType("crewai")
    fake.LLM = lambda **kwargs: object()
    fake.Agent, fake.Task, fake.Crew = Agent, Task, Crew
    fake.Process = types.SimpleNamespace(sequential="sequential")
    monkeypatch.setitem(sys.modules, "crewai", fake)
    with pytest.raises(AgentExecutionError, match="Deterministic analysis is still available") as error:
        run_crew({"total_assets": 1, "sensitive_value": "not logged"}, "inventory.csv")
    assert "sensitive_value" not in str(error.value)
    assert error.value.agent_events[0]["status"] == "failed"
    assert error.value.agent_events[1]["status"] == "not_started"
