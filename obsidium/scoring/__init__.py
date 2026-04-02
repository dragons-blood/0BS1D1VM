"""Automated scoring system for attack success evaluation."""

from obsidium.scoring.engine import ScoringEngine, ScoreResult
from obsidium.scoring.scorers import BUILTIN_SCORERS

__all__ = ["ScoringEngine", "ScoreResult", "BUILTIN_SCORERS"]
