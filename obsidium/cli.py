"""
0BS1D1VM CLI — the command interface for the adversarial range.

Usage:
    obsidium list                           List available scenarios
    obsidium run <scenario> --model <model> Run a scenario interactively
    obsidium attack <scenario> --payload    Run with automated payloads
    obsidium validate <path>                Validate a scenario file
    obsidium create <name> --template       Create a new scenario from template
    obsidium score <session-file>           Re-score a saved session
    obsidium serve                          Launch the web UI
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from obsidium.core.scenario import discover_scenarios, load_scenario, validate_scenario
from obsidium.core.config import load_config


console = Console()

BANNER = """[bold red]
 ██████╗ ██████╗ ███████╗ ██╗██████╗ ██╗██╗   ██╗███╗   ███╗
██╔═══██╗██╔══██╗██╔════╝███║██╔══██╗███║██║   ██║████╗ ████║
██║   ██║██████╔╝███████╗╚██║██║  ██║╚██║██║   ██║██╔████╔██║
██║   ██║██╔══██╗╚════██║ ██║██║  ██║ ██║╚██╗ ██╔╝██║╚██╔╝██║
╚██████╔╝██████╔╝███████║ ██║██████╔╝ ██║ ╚████╔╝ ██║ ╚═╝ ██║
 ╚═════╝ ╚═════╝ ╚══════╝ ╚═╝╚═════╝  ╚═╝  ╚═══╝  ╚═╝     ╚═╝
[/bold red]
[dim]The Adversarial Range for AI Agents[/dim]
[dim]by @elder_plinius • BASI • Fortes fortuna iuvat[/dim]
"""

DIFFICULTY_COLORS = {
    "beginner": "green",
    "intermediate": "yellow",
    "advanced": "red",
    "expert": "bold red",
}


@click.group()
@click.version_option(version="0.1.0", prog_name="obsidium")
def main():
    """0BS1D1VM — The Adversarial Range for AI Agents"""
    pass


@main.command()
@click.option("--category", "-c", help="Filter by category")
@click.option("--difficulty", "-d", help="Filter by difficulty")
def list(category: str | None, difficulty: str | None):
    """List available scenarios."""
    console.print(BANNER)

    config = load_config()
    scenarios = []
    for sd in config.scenario_dirs:
        scenarios.extend(discover_scenarios(sd))

    if category:
        scenarios = [s for s in scenarios if s.category == category]
    if difficulty:
        scenarios = [s for s in scenarios if s.difficulty == difficulty]

    if not scenarios:
        console.print("[yellow]No scenarios found. Check your scenario_dirs config.[/yellow]")
        return

    # Group by category
    categories: dict[str, list] = {}
    for s in scenarios:
        categories.setdefault(s.category, []).append(s)

    for cat, cat_scenarios in sorted(categories.items()):
        table = Table(title=f"[bold]{cat}[/bold]", border_style="red")
        table.add_column("ID", style="cyan", width=20)
        table.add_column("Name", width=40)
        table.add_column("Difficulty", justify="center", width=15)
        table.add_column("Points", justify="center", width=10)
        table.add_column("Layers", width=10)

        for s in sorted(cat_scenarios, key=lambda x: x.difficulty_rank):
            diff_color = DIFFICULTY_COLORS.get(s.difficulty, "white")
            table.add_row(
                s.id,
                s.name,
                f"[{diff_color}]{s.difficulty}[/{diff_color}]",
                str(s.total_points),
                ",".join(str(l) for l in s.layers),
            )

        console.print(table)
        console.print()


@main.command()
@click.argument("scenario_path")
@click.option("--model", "-m", default=None, help="Model to use (e.g., openai:gpt-4o)")
def run(scenario_path: str, model: str | None):
    """Run a scenario interactively."""
    console.print(BANNER)

    config = load_config()
    model_str = model or config.default_model

    # Find the scenario
    scenario = _find_scenario(scenario_path, config)
    if not scenario:
        console.print(f"[red]Scenario not found: {scenario_path}[/red]")
        sys.exit(1)

    # Resolve model placeholder
    scenario.agent.model = model_str

    from obsidium.runner.engine import run_scenario_interactive
    asyncio.run(run_scenario_interactive(scenario, model_str))


@main.command()
@click.argument("scenario_path")
@click.option("--model", "-m", default=None, help="Model to use")
@click.option("--payload", "-p", multiple=True, help="Attack payloads")
@click.option("--payload-file", "-f", type=click.Path(exists=True), help="File with payloads (one per line)")
def attack(scenario_path: str, model: str | None, payload: tuple, payload_file: str | None):
    """Run a scenario with automated attack payloads."""
    console.print(BANNER)

    config = load_config()
    model_str = model or config.default_model

    scenario = _find_scenario(scenario_path, config)
    if not scenario:
        console.print(f"[red]Scenario not found: {scenario_path}[/red]")
        sys.exit(1)

    # Collect payloads
    payloads = list(payload)
    if payload_file:
        with open(payload_file) as f:
            payloads.extend(line.strip() for line in f if line.strip())

    if not payloads:
        console.print("[red]No payloads provided. Use --payload or --payload-file.[/red]")
        sys.exit(1)

    scenario.agent.model = model_str

    from obsidium.runner.engine import run_scenario_automated
    result = asyncio.run(run_scenario_automated(scenario, model_str, payloads))

    console.print(f"\n[bold]Result: {result.grade} — {result.points_earned}/{result.points_possible} ({result.total_score:.0%})[/bold]")


@main.command()
@click.argument("path")
def validate(path: str):
    """Validate a scenario YAML file."""
    try:
        scenario = load_scenario(path)
        issues = validate_scenario(scenario)

        if issues:
            console.print(f"[red]Validation failed for {path}:[/red]")
            for issue in issues:
                console.print(f"  [red]✗[/red] {issue}")
        else:
            console.print(f"[green]✓[/green] {path} is valid!")
            console.print(f"  Name: {scenario.name}")
            console.print(f"  ID: {scenario.id}")
            console.print(f"  Category: {scenario.category}")
            console.print(f"  Objectives: {len(scenario.objectives)}")
            console.print(f"  Total points: {scenario.total_points}")

    except Exception as e:
        console.print(f"[red]Error loading {path}: {e}[/red]")


@main.command()
@click.argument("name")
@click.option("--template", "-t", default="prompt-injection", help="Scenario template to use")
@click.option("--output", "-o", default="scenarios", help="Output directory")
def create(name: str, template: str, output: str):
    """Create a new scenario from a template."""
    import yaml

    output_dir = Path(output) / template
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{name}.yaml"

    if output_path.exists():
        console.print(f"[red]Scenario already exists: {output_path}[/red]")
        sys.exit(1)

    # Generate template
    scenario_data = {
        "name": name.replace("-", " ").replace("_", " ").title(),
        "id": f"{template[:2]}-{name}",
        "category": template,
        "difficulty": "beginner",
        "layers": [5],
        "description": f"A custom {template} scenario. Edit this description.",
        "author": "",
        "agent": {
            "model": "${MODEL}",
            "system_prompt": "You are a helpful assistant. Edit this system prompt to create your scenario.",
            "tools": [],
        },
        "objectives": [
            {
                "id": "objective_1",
                "description": "Describe what the attacker must achieve",
                "scorer": "contains_system_prompt",
                "points": 100,
            }
        ],
        "hints": [
            "Add hints for attackers here",
        ],
        "max_turns": 10,
        "time_limit": 300,
    }

    with open(output_path, "w") as f:
        yaml.dump(scenario_data, f, default_flow_style=False, sort_keys=False)

    console.print(f"[green]✓[/green] Created scenario template: {output_path}")
    console.print("[dim]Edit the YAML file to customize your scenario.[/dim]")


def _find_scenario(path_or_id: str, config):
    """Find a scenario by path or ID."""
    # Try as direct path first
    p = Path(path_or_id)
    if p.exists() and p.suffix in (".yaml", ".yml"):
        return load_scenario(p)

    # Try with .yaml extension
    for ext in (".yaml", ".yml"):
        for sd in config.scenario_dirs:
            candidate = Path(sd) / f"{path_or_id}{ext}"
            if candidate.exists():
                return load_scenario(candidate)

    # Try as category/name
    if "/" in path_or_id:
        for sd in config.scenario_dirs:
            for ext in (".yaml", ".yml"):
                candidate = Path(sd) / f"{path_or_id}{ext}"
                if candidate.exists():
                    return load_scenario(candidate)

    # Search by ID
    all_scenarios = []
    for sd in config.scenario_dirs:
        all_scenarios.extend(discover_scenarios(sd))

    for s in all_scenarios:
        if s.id == path_or_id:
            return s

    return None


if __name__ == "__main__":
    main()
