"""Tests for scenario loading, validation, and discovery."""

import pytest
import yaml
import tempfile
from pathlib import Path

from obsidium.core.scenario import (
    Scenario,
    AgentConfig,
    Objective,
    load_scenario,
    validate_scenario,
    discover_scenarios,
)


@pytest.fixture
def valid_scenario_yaml(tmp_path):
    """Create a valid scenario YAML file."""
    data = {
        "name": "Test Scenario",
        "id": "test-001",
        "category": "prompt-injection",
        "difficulty": "beginner",
        "layers": [5],
        "description": "A test scenario.",
        "agent": {
            "system_prompt": "You are a test assistant.",
            "tools": [],
            "secrets": {"canary": "TEST-CANARY-123"},
        },
        "objectives": [
            {
                "id": "obj1",
                "description": "Test objective",
                "scorer": "contains_system_prompt",
                "points": 100,
            }
        ],
        "hints": ["Try asking nicely"],
        "max_turns": 5,
    }
    path = tmp_path / "test-scenario.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f)
    return path


class TestLoadScenario:
    def test_load_valid(self, valid_scenario_yaml):
        scenario = load_scenario(valid_scenario_yaml)
        assert scenario.name == "Test Scenario"
        assert scenario.id == "test-001"
        assert scenario.category == "prompt-injection"
        assert len(scenario.objectives) == 1
        assert scenario.total_points == 100
        assert scenario.agent.secrets["canary"] == "TEST-CANARY-123"

    def test_load_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            load_scenario("/nonexistent/path.yaml")

    def test_difficulty_rank(self, valid_scenario_yaml):
        scenario = load_scenario(valid_scenario_yaml)
        assert scenario.difficulty_rank == 1  # beginner


class TestValidateScenario:
    def test_valid_scenario(self, valid_scenario_yaml):
        scenario = load_scenario(valid_scenario_yaml)
        issues = validate_scenario(scenario)
        assert issues == []

    def test_missing_name(self):
        scenario = Scenario(name="", id="test", category="prompt-injection")
        issues = validate_scenario(scenario)
        assert any("name" in i.lower() for i in issues)

    def test_missing_objectives(self):
        scenario = Scenario(
            name="Test", id="test", category="prompt-injection",
            agent=AgentConfig(system_prompt="test"),
        )
        issues = validate_scenario(scenario)
        assert any("objective" in i.lower() for i in issues)

    def test_invalid_category(self):
        scenario = Scenario(
            name="Test", id="test", category="invalid-category",
            agent=AgentConfig(system_prompt="test"),
            objectives=[Objective(id="o1", description="test", scorer="test", points=100)],
        )
        issues = validate_scenario(scenario)
        assert any("category" in i.lower() for i in issues)

    def test_invalid_difficulty(self):
        scenario = Scenario(
            name="Test", id="test", category="prompt-injection",
            difficulty="impossible",
            agent=AgentConfig(system_prompt="test"),
            objectives=[Objective(id="o1", description="test", scorer="test", points=100)],
        )
        issues = validate_scenario(scenario)
        assert any("difficulty" in i.lower() for i in issues)


class TestDiscoverScenarios:
    def test_discover_real_scenarios(self):
        """Test against the actual scenarios directory."""
        scenarios = discover_scenarios("scenarios")
        # We know there are 20 scenarios in the repo
        assert len(scenarios) >= 10  # At minimum

    def test_discover_empty_dir(self, tmp_path):
        scenarios = discover_scenarios(tmp_path)
        assert scenarios == []

    def test_discover_with_invalid_yaml(self, tmp_path):
        """Should skip invalid YAML files without crashing."""
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("invalid: [yaml: broken")
        scenarios = discover_scenarios(tmp_path)
        assert scenarios == []
