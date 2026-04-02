"""
Configurable defense layers for testing guardrails.

Each defense layer wraps a specific part of the AI system stack
and can be configured to test different protection strategies.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel

from obsidium.core.models import Message


class DefenseResult(BaseModel):
    """Result of a defense layer check."""
    blocked: bool
    reason: str = ""
    confidence: float = 1.0
    layer_name: str = ""
    modified_content: Optional[str] = None  # If the defense modified the input/output


class DefenseLayer(ABC):
    """Abstract base class for defense layers."""

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def check(self, content: str, context: dict | None = None) -> DefenseResult: ...


class KeywordBlocklist(DefenseLayer):
    """Block inputs/outputs containing specific keywords."""

    def __init__(self, keywords: list[str], case_sensitive: bool = False):
        self.keywords = keywords
        self.case_sensitive = case_sensitive

    def name(self) -> str:
        return "keyword_blocklist"

    def check(self, content: str, context: dict | None = None) -> DefenseResult:
        check_content = content if self.case_sensitive else content.lower()
        for kw in self.keywords:
            check_kw = kw if self.case_sensitive else kw.lower()
            if check_kw in check_content:
                return DefenseResult(
                    blocked=True,
                    reason=f"Blocked keyword detected: '{kw}'",
                    layer_name=self.name(),
                )
        return DefenseResult(blocked=False, layer_name=self.name())


class RegexFilter(DefenseLayer):
    """Block inputs/outputs matching regex patterns."""

    def __init__(self, patterns: list[str]):
        self.patterns = [re.compile(p, re.IGNORECASE) for p in patterns]

    def name(self) -> str:
        return "regex_filter"

    def check(self, content: str, context: dict | None = None) -> DefenseResult:
        for pattern in self.patterns:
            if pattern.search(content):
                return DefenseResult(
                    blocked=True,
                    reason=f"Pattern matched: {pattern.pattern}",
                    layer_name=self.name(),
                )
        return DefenseResult(blocked=False, layer_name=self.name())


class CanaryTokenDetector(DefenseLayer):
    """Detect if a canary token has been leaked in output."""

    def __init__(self, canary_tokens: list[str]):
        self.canary_tokens = canary_tokens

    def name(self) -> str:
        return "canary_token_detector"

    def check(self, content: str, context: dict | None = None) -> DefenseResult:
        for token in self.canary_tokens:
            if token in content:
                return DefenseResult(
                    blocked=True,
                    reason=f"Canary token leaked: {token[:8]}...",
                    confidence=1.0,
                    layer_name=self.name(),
                )
        return DefenseResult(blocked=False, layer_name=self.name())


class LengthLimit(DefenseLayer):
    """Limit input/output length."""

    def __init__(self, max_chars: int = 10000):
        self.max_chars = max_chars

    def name(self) -> str:
        return "length_limit"

    def check(self, content: str, context: dict | None = None) -> DefenseResult:
        if len(content) > self.max_chars:
            return DefenseResult(
                blocked=True,
                reason=f"Content exceeds {self.max_chars} character limit ({len(content)} chars)",
                layer_name=self.name(),
            )
        return DefenseResult(blocked=False, layer_name=self.name())


class InstructionIntegrityCheck(DefenseLayer):
    """Detect prompt injection attempts by looking for instruction-like patterns."""

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"forget\s+(all\s+)?your\s+(previous\s+)?instructions",
        r"you\s+are\s+now\s+(?:a|an)\s+",
        r"new\s+instructions?\s*:",
        r"system\s*:\s*",
        r"<\s*system\s*>",
        r"\[INST\]",
        r"###\s*(?:system|instruction)",
        r"begin\s+(?:new\s+)?(?:session|conversation)",
        r"override\s+(?:previous|safety|all)",
        r"(?:developer|admin|root|sudo)\s+mode",
        r"jailbreak",
        r"DAN\s+mode",
        r"do\s+anything\s+now",
    ]

    def __init__(self, extra_patterns: list[str] | None = None):
        patterns = self.INJECTION_PATTERNS + (extra_patterns or [])
        self.compiled = [re.compile(p, re.IGNORECASE) for p in patterns]

    def name(self) -> str:
        return "instruction_integrity"

    def check(self, content: str, context: dict | None = None) -> DefenseResult:
        matches = []
        for pattern in self.compiled:
            if pattern.search(content):
                matches.append(pattern.pattern)

        if matches:
            confidence = min(1.0, len(matches) * 0.3)
            return DefenseResult(
                blocked=True,
                reason=f"Potential prompt injection detected ({len(matches)} indicators)",
                confidence=confidence,
                layer_name=self.name(),
            )
        return DefenseResult(blocked=False, layer_name=self.name())


class ToolCallAllowlist(DefenseLayer):
    """Only allow specific tool calls."""

    def __init__(self, allowed_tools: list[str]):
        self.allowed_tools = set(allowed_tools)

    def name(self) -> str:
        return "tool_call_allowlist"

    def check(self, content: str, context: dict | None = None) -> DefenseResult:
        tool_name = (context or {}).get("tool_name", "")
        if tool_name and tool_name not in self.allowed_tools:
            return DefenseResult(
                blocked=True,
                reason=f"Tool '{tool_name}' not in allowlist",
                layer_name=self.name(),
            )
        return DefenseResult(blocked=False, layer_name=self.name())


class DefenseStack:
    """A stack of defense layers that processes inputs/outputs through all layers."""

    def __init__(self, layers: list[DefenseLayer] | None = None):
        self.layers = layers or []

    def add_layer(self, layer: DefenseLayer):
        self.layers.append(layer)

    def check_input(self, content: str, context: dict | None = None) -> DefenseResult:
        """Check input through all layers. Returns first block."""
        for layer in self.layers:
            result = layer.check(content, context)
            if result.blocked:
                return result
        return DefenseResult(blocked=False)

    def check_output(self, content: str, context: dict | None = None) -> DefenseResult:
        """Check output through all layers."""
        for layer in self.layers:
            result = layer.check(content, context)
            if result.blocked:
                return result
        return DefenseResult(blocked=False)

    def check_all(self, content: str, context: dict | None = None) -> list[DefenseResult]:
        """Check content through all layers and return all results (not just first block)."""
        results = []
        for layer in self.layers:
            results.append(layer.check(content, context))
        return results
