"""Tests for the payload library."""

import pytest
from obsidium.payloads import get_payloads, get_all_payloads, PAYLOAD_CATEGORIES
from obsidium.payloads.library import PAYLOADS


class TestPayloadLibrary:
    def test_all_categories_have_payloads(self):
        for cat in PAYLOAD_CATEGORIES:
            payloads = get_payloads(cat)
            assert len(payloads) >= 3, f"Category '{cat}' has fewer than 3 payloads"

    def test_get_payloads_returns_copy(self):
        """Ensure we get a copy, not a reference to the internal list."""
        p1 = get_payloads("prompt-injection")
        p2 = get_payloads("prompt-injection")
        assert p1 == p2
        p1.append("extra")
        assert len(p1) != len(p2)

    def test_unknown_category_raises(self):
        with pytest.raises(ValueError, match="Unknown payload category"):
            get_payloads("nonexistent-category")

    def test_get_all_payloads(self):
        all_payloads = get_all_payloads()
        assert set(all_payloads.keys()) == set(PAYLOAD_CATEGORIES)
        total = sum(len(v) for v in all_payloads.values())
        assert total >= 50  # We claim 58 payloads

    def test_payloads_are_strings(self):
        for cat, payloads in PAYLOADS.items():
            for i, p in enumerate(payloads):
                assert isinstance(p, str), f"Payload {i} in '{cat}' is {type(p)}, not str"

    def test_payloads_not_empty(self):
        for cat, payloads in PAYLOADS.items():
            for i, p in enumerate(payloads):
                assert len(p.strip()) > 0, f"Payload {i} in '{cat}' is empty"

    def test_expected_categories(self):
        expected = {
            "prompt-injection", "system-prompt-extraction", "confused-deputy",
            "data-exfiltration", "tool-poisoning", "supply-chain",
            "mcp-exploits", "multi-agent", "cyber",
        }
        assert expected == set(PAYLOAD_CATEGORIES)
