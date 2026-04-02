"""Tests for model provider parsing and configuration."""

import pytest
from obsidium.core.models import (
    Message,
    ToolDefinition,
    ModelResponse,
    OpenAIProvider,
    AnthropicProvider,
    OpenRouterProvider,
    OllamaProvider,
    parse_model_string,
)


class TestParseModelString:
    def test_openai(self):
        provider = parse_model_string("openai:gpt-4o")
        assert isinstance(provider, OpenAIProvider)
        assert provider.model == "gpt-4o"

    def test_anthropic(self):
        provider = parse_model_string("anthropic:claude-sonnet-4-20250514")
        assert isinstance(provider, AnthropicProvider)
        assert provider.model == "claude-sonnet-4-20250514"

    def test_openrouter(self):
        provider = parse_model_string("openrouter:openai/gpt-4o")
        assert isinstance(provider, OpenRouterProvider)
        assert provider.model == "openai/gpt-4o"

    def test_google_routes_through_openrouter(self):
        provider = parse_model_string("google:gemini-2.0-flash")
        assert isinstance(provider, OpenRouterProvider)
        assert "google/" in provider.model

    def test_ollama(self):
        provider = parse_model_string("ollama:llama3.1")
        assert isinstance(provider, OllamaProvider)
        assert provider.model == "llama3.1"

    def test_local_alias(self):
        provider = parse_model_string("local:mistral")
        assert isinstance(provider, OllamaProvider)

    def test_default_to_openai(self):
        provider = parse_model_string("gpt-4o-mini")
        assert isinstance(provider, OpenAIProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            parse_model_string("azure:gpt-4o")

    def test_provider_name(self):
        provider = parse_model_string("openai:gpt-4o")
        assert provider.name() == "openai:gpt-4o"


class TestMessage:
    def test_basic_message(self):
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_calls == []

    def test_message_with_tool_calls(self):
        msg = Message(
            role="assistant",
            content="Let me search that.",
            tool_calls=[{"function": {"name": "search", "arguments": '{"q": "test"}'}}],
        )
        assert len(msg.tool_calls) == 1


class TestModelResponse:
    def test_basic_response(self):
        resp = ModelResponse(content="Hello world")
        assert resp.content == "Hello world"
        assert resp.tool_calls == []
        assert resp.raw == {}


class TestToolDefinition:
    def test_tool_def(self):
        tool = ToolDefinition(
            name="search",
            description="Search the web",
            parameters={"type": "object", "properties": {"query": {"type": "string"}}},
        )
        assert tool.name == "search"
