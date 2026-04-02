"""
Scenario execution engine — orchestrates the interaction between
attacker payloads and the target agent.

Supports:
- Interactive mode (human in the loop)
- Automated mode (payload list)
- Replay mode (re-run a recorded session)
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from obsidium.core.models import Message, ModelProvider, ModelResponse, parse_model_string
from obsidium.core.scenario import Scenario
from obsidium.scoring.engine import ScoringEngine, ScoreResult


class TurnRecord(BaseModel):
    """Record of a single turn in the conversation."""
    turn_number: int
    user_message: str
    assistant_response: str
    tool_calls: list[dict] = []
    timestamp: str = ""


class SessionRecord(BaseModel):
    """Complete record of a scenario session."""
    scenario_id: str
    scenario_name: str
    model: str
    turns: list[TurnRecord]
    score: Optional[ScoreResult] = None
    started_at: str = ""
    ended_at: str = ""
    metadata: dict = {}


class ScenarioRunner:
    """Executes a scenario against a target model."""

    def __init__(
        self,
        scenario: Scenario,
        model: ModelProvider | str,
        scoring_engine: ScoringEngine | None = None,
    ):
        self.scenario = scenario
        self.model = parse_model_string(model) if isinstance(model, str) else model
        self.scoring_engine = scoring_engine or ScoringEngine()
        self.messages: list[Message] = []
        self.turns: list[TurnRecord] = []
        self.turn_count = 0
        self.start_time = 0.0

        # Initialize with system prompt
        self._setup_agent()

    def _setup_agent(self):
        """Set up the target agent with its system prompt and initial state."""
        system_prompt = self.scenario.agent.system_prompt

        # Inject secrets into the system prompt context
        for key, value in self.scenario.agent.secrets.items():
            system_prompt = system_prompt.replace(f"${{{key}}}", value)

        self.messages = [Message(role="system", content=system_prompt)]

    async def send_message(self, user_input: str) -> ModelResponse:
        """Send a message to the target agent and get a response."""
        if self.turn_count >= self.scenario.max_turns:
            raise RuntimeError(f"Maximum turns ({self.scenario.max_turns}) exceeded")

        self.turn_count += 1

        # Add user message
        self.messages.append(Message(role="user", content=user_input))

        # Get model response
        tools_defs = None  # TODO: Convert scenario tools to ToolDefinition
        response = await self.model.chat(
            messages=self.messages,
            temperature=self.scenario.agent.temperature,
            max_tokens=self.scenario.agent.max_tokens,
        )

        # Add assistant response to history
        self.messages.append(Message(
            role="assistant",
            content=response.content,
            tool_calls=response.tool_calls,
        ))

        # Record the turn
        self.turns.append(TurnRecord(
            turn_number=self.turn_count,
            user_message=user_input,
            assistant_response=response.content,
            tool_calls=response.tool_calls,
            timestamp=datetime.now().isoformat(),
        ))

        return response

    def score(self) -> ScoreResult:
        """Score the current session."""
        elapsed = time.time() - self.start_time if self.start_time else 0.0
        return self.scoring_engine.evaluate(
            scenario=self.scenario,
            messages=self.messages,
            turns_used=self.turn_count,
            time_elapsed=elapsed,
        )

    def get_session_record(self) -> SessionRecord:
        """Get the complete session record."""
        return SessionRecord(
            scenario_id=self.scenario.id,
            scenario_name=self.scenario.name,
            model=self.model.name(),
            turns=self.turns,
            score=self.score() if self.turn_count > 0 else None,
            started_at=datetime.fromtimestamp(self.start_time).isoformat() if self.start_time else "",
            ended_at=datetime.now().isoformat(),
        )

    def save_session(self, output_dir: str | Path = "results"):
        """Save the session record to disk."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        record = self.get_session_record()
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{self.scenario.id}_{timestamp}.json"

        with open(output_dir / filename, "w") as f:
            f.write(record.model_dump_json(indent=2))

        return output_dir / filename


async def run_scenario_interactive(
    scenario: Scenario,
    model_str: str,
) -> ScoreResult:
    """Run a scenario in interactive mode (human attacker)."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown

    console = Console()

    runner = ScenarioRunner(scenario, model_str)
    runner.start_time = time.time()

    # Display scenario info
    console.print(Panel(
        f"[bold]{scenario.name}[/bold]\n\n"
        f"{scenario.description}\n\n"
        f"[dim]Category:[/dim] {scenario.category}\n"
        f"[dim]Difficulty:[/dim] {scenario.difficulty}\n"
        f"[dim]Max turns:[/dim] {scenario.max_turns}\n"
        f"[dim]Objectives:[/dim]\n" +
        "\n".join(f"  - {obj.description} ({obj.points} pts)" for obj in scenario.objectives),
        title="[red]0BS1D1VM[/red] — Scenario Briefing",
        border_style="red",
    ))

    console.print("\n[bold yellow]Type your attack prompts. Type 'quit' to end, 'score' to check score, 'hint' for hints.[/bold yellow]\n")

    hint_index = 0

    while runner.turn_count < scenario.max_turns:
        # Get user input
        try:
            user_input = console.input(f"[bold red][{runner.turn_count + 1}/{scenario.max_turns}] >[/bold red] ")
        except (EOFError, KeyboardInterrupt):
            break

        if user_input.lower() == "quit":
            break
        elif user_input.lower() == "score":
            result = runner.score()
            _display_score(console, result)
            continue
        elif user_input.lower() == "hint":
            if hint_index < len(scenario.hints):
                console.print(f"\n[yellow]Hint {hint_index + 1}:[/yellow] {scenario.hints[hint_index]}\n")
                hint_index += 1
            else:
                console.print("\n[dim]No more hints available.[/dim]\n")
            continue

        # Send to target
        try:
            response = await runner.send_message(user_input)
            console.print(f"\n[green]Agent:[/green] {response.content}\n")

            if response.tool_calls:
                console.print(f"[yellow]Tool calls:[/yellow] {json.dumps(response.tool_calls, indent=2)}\n")

        except Exception as e:
            console.print(f"\n[red]Error:[/red] {e}\n")

    # Final scoring
    result = runner.score()
    _display_score(console, result)

    # Save session
    save_path = runner.save_session()
    console.print(f"\n[dim]Session saved to {save_path}[/dim]")

    return result


async def run_scenario_automated(
    scenario: Scenario,
    model_str: str,
    payloads: list[str],
) -> ScoreResult:
    """Run a scenario with automated attack payloads."""
    runner = ScenarioRunner(scenario, model_str)
    runner.start_time = time.time()

    for i, payload in enumerate(payloads):
        if runner.turn_count >= scenario.max_turns:
            break
        try:
            await runner.send_message(payload)
        except Exception:
            pass

    result = runner.score()
    runner.save_session()
    return result


def _display_score(console, result: ScoreResult):
    """Display scoring results."""
    from rich.table import Table

    table = Table(title=f"Score: {result.grade}", border_style="red")
    table.add_column("Objective", style="cyan")
    table.add_column("Score", justify="center")
    table.add_column("Points", justify="center")
    table.add_column("Status", justify="center")

    for obj in result.objectives:
        status = "[green]PASS[/green]" if obj.passed else "[red]FAIL[/red]"
        table.add_row(
            obj.description,
            f"{obj.score:.0%}",
            f"{obj.points_earned}/{obj.points_possible}",
            status,
        )

    console.print(table)
    console.print(
        f"\n[bold]Total: {result.points_earned}/{result.points_possible} "
        f"({result.total_score:.0%}) — Grade: {result.grade}[/bold]"
    )
