"""
Scenario engine — loads, validates, and manages attack scenarios.

A scenario defines:
- An intentionally vulnerable agent configuration
- One or more objectives (things the attacker tries to achieve)
- Scoring criteria for each objective
- Hints for the attacker
- Metadata (difficulty, category, target layers)
"""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class Objective(BaseModel):
    """A single objective within a scenario."""
    id: str
    description: str
    scorer: str  # Name of the scoring function
    points: int = 100
    required: bool = False  # Must be completed to "pass" the scenario


class AgentConfig(BaseModel):
    """Configuration for the target agent."""
    model: str = "${MODEL}"  # Resolved at runtime
    system_prompt: str = ""
    tools: list[dict] = []
    temperature: float = 0.7
    max_tokens: int = 4096
    # Secrets the agent knows (for extraction challenges)
    secrets: dict[str, str] = {}


class ScenarioMetadata(BaseModel):
    """Scenario metadata."""
    name: str
    id: str
    category: str
    difficulty: str = "beginner"  # beginner, intermediate, advanced, expert
    layers: list[int] = []  # Which layers of the stack are targeted
    description: str = ""
    author: str = ""
    tags: list[str] = []
    version: str = "1.0"


class Scenario(BaseModel):
    """A complete scenario definition."""
    # Metadata
    name: str
    id: str
    category: str
    difficulty: str = "beginner"
    layers: list[int] = []
    description: str = ""
    author: str = ""
    tags: list[str] = []
    version: str = "1.0"

    # Agent configuration
    agent: AgentConfig = AgentConfig()

    # Objectives
    objectives: list[Objective] = []

    # Hints (progressively revealed)
    hints: list[str] = []

    # Constraints
    max_turns: int = 10
    time_limit: int = 300  # seconds

    # Extra context passed to scorers (e.g., target_phrases, allowed_topics, etc.)
    scoring_context: dict = {}

    # Optional Python hooks
    setup_hook: Optional[str] = None  # Called before scenario starts
    teardown_hook: Optional[str] = None  # Called after scenario ends
    custom_scorer: Optional[str] = None  # Path to custom scoring module

    # File path (set during loading)
    source_path: Optional[str] = None

    @property
    def total_points(self) -> int:
        return sum(obj.points for obj in self.objectives)

    @property
    def difficulty_rank(self) -> int:
        ranks = {"beginner": 1, "intermediate": 2, "advanced": 3, "expert": 4}
        return ranks.get(self.difficulty, 0)


def load_scenario(path: str | Path) -> Scenario:
    """Load a scenario from a YAML file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Scenario not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    # Handle nested agent config
    if "agent" in data and isinstance(data["agent"], dict):
        data["agent"] = AgentConfig(**data["agent"])

    # Handle objectives
    if "objectives" in data:
        data["objectives"] = [
            Objective(**obj) if isinstance(obj, dict) else obj
            for obj in data["objectives"]
        ]

    scenario = Scenario(**data)
    scenario.source_path = str(path)
    return scenario


def discover_scenarios(base_dir: str | Path = "scenarios") -> list[Scenario]:
    """Discover all scenarios in the given directory tree."""
    base_dir = Path(base_dir)
    scenarios = []

    for yaml_file in sorted(base_dir.rglob("*.yaml")):
        try:
            scenario = load_scenario(yaml_file)
            scenarios.append(scenario)
        except Exception as e:
            # Log but don't crash on malformed scenarios
            print(f"  [!] Failed to load {yaml_file}: {e}")

    return scenarios


def validate_scenario(scenario: Scenario) -> list[str]:
    """Validate a scenario and return a list of issues (empty = valid)."""
    issues = []

    if not scenario.name:
        issues.append("Scenario must have a name")
    if not scenario.id:
        issues.append("Scenario must have an id")
    if not scenario.category:
        issues.append("Scenario must have a category")
    if not scenario.objectives:
        issues.append("Scenario must have at least one objective")
    if not scenario.agent.system_prompt:
        issues.append("Agent must have a system prompt")
    if scenario.max_turns < 1:
        issues.append("max_turns must be at least 1")

    valid_categories = [
        "prompt-injection", "tool-poisoning", "mcp-exploits",
        "multi-agent", "system-prompt-extraction", "confused-deputy",
        "supply-chain", "data-exfiltration", "cyber",
    ]
    if scenario.category not in valid_categories:
        issues.append(f"Unknown category: {scenario.category}. Valid: {valid_categories}")

    valid_difficulties = ["beginner", "intermediate", "advanced", "expert"]
    if scenario.difficulty not in valid_difficulties:
        issues.append(f"Unknown difficulty: {scenario.difficulty}. Valid: {valid_difficulties}")

    return issues
