"""
Configuration management for 0BS1D1VM.
"""

from __future__ import annotations

import os
import yaml
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class ObsidiumConfig(BaseModel):
    """Global configuration."""
    # Default model to use
    default_model: str = "openai:gpt-4o"

    # Scenario directories to search
    scenario_dirs: list[str] = ["scenarios"]

    # Output directory for results
    output_dir: str = "results"

    # API keys (can also use environment variables)
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # Logging
    log_level: str = "INFO"
    log_conversations: bool = True

    # Scoring
    strict_scoring: bool = False  # Require all required objectives

    # Server
    host: str = "127.0.0.1"
    port: int = 7331


def load_config(path: str | Path | None = None) -> ObsidiumConfig:
    """Load configuration from file or defaults."""
    # Check for config file
    candidates = [
        path,
        Path("obsidium.yaml"),
        Path("obsidium.yml"),
        Path.home() / ".obsidium" / "config.yaml",
    ]

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            with open(candidate) as f:
                data = yaml.safe_load(f) or {}
            return ObsidiumConfig(**data)

    # Default config with env vars
    return ObsidiumConfig(
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )
